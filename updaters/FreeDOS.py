

import glob
import re
import os
from functools import cache
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.shared.parse_hash import parse_hash
from updaters.shared.robust_download import robust_download
from updaters.shared.robust_get import robust_get
from updaters.shared.fetch_expected_file_size import fetch_expected_file_size
from updaters.shared.extract_file_from_zip import extract_file_from_zip

DOMAIN = "https://www.ibiblio.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/pub/micro/pc-stuff/freedos/files/distributions"
FILE_NAME = "FreeDOS-[[VER]]-[[EDITION]].[[EXT]]"
ISOname = "FreeDOS"

class FreeDOS(GenericUpdater):

    def install_latest_version(self) -> bool | None:
        """
        Download and install the latest version of the software.
        """
        download_link = self._get_download_link()
        if not download_link:
            return None
        new_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(new_file, Path):
            return None
        archive_path = new_file.with_suffix(".zip")
        # Download the archive using robust_download with increased retries for transient 404 errors
        success = robust_download(download_link, archive_path, retries=max(self.retries_count, 5), delay=2, logging_callback=self.logging_callback)
        if not success:
            self.logging_callback(f"[{ISOname}] Failed to download archive from {download_link}")
            return None
        # Integrity check for the archive (zip file)
        latest_version = self._get_latest_version()
        if latest_version is None:
            self.logging_callback(f"[{ISOname}.install_latest_version] No latest version found.")
            return None
        latest_version_str = self._version_to_str(latest_version).lstrip("/")
        checksums_url = f"{DOWNLOAD_PAGE_URL}/{latest_version_str}/verify.txt"
        # File size check
        download_url = self._get_download_link()
        expected_size = fetch_expected_file_size(download_url)
        if expected_size is not None:
            if not archive_path.exists():
                self.logging_callback(f"[{ISOname}.install_latest_version] Archive does not exist: {archive_path}")
                return False
            actual_size = archive_path.stat().st_size
            if actual_size != expected_size:
                self.logging_callback(f"[{ISOname}.install_latest_version] Archive size mismatch. Actual: {actual_size}, Expected: {expected_size}")
                return False
        resp = robust_get(checksums_url, retries=max(self.retries_count, 5), delay=2, logging_callback=self.logging_callback)
        if resp is None or getattr(resp, 'status_code', 200) != 200:
            self.logging_callback(f"[{ISOname}] Could not fetch verify.txt from {checksums_url}")
            return False
        try:
            sha256_sums = next(sums for sums in resp.text.split("\n\n") if "sha256" in sums)
        except StopIteration:
            self.logging_callback(f"[{ISOname}] Could not find the sha256 hash in the hash list file")
            return False
        sha256_sum = parse_hash(sha256_sums, [self.edition], 0, logging_callback=self.logging_callback)
        if not sha256_sum:
            self.logging_callback(f"[{ISOname}.install_latest_version] No sha256 sum found for edition {self.edition}.")
            return False
        from updaters.shared.sha256_hash_check import sha256_hash_check
        if not sha256_hash_check(archive_path, sha256_sum, package_name=ISOname, logging_callback=self.logging_callback):
            self.logging_callback(f"[{ISOname}.install_latest_version] Archive hash check failed.")
            return False
        # Extract only the ISO or IMG file from the archive using extract_file_from_zip
        import zipfile
        with zipfile.ZipFile(archive_path) as z:
            file_list = z.namelist()
            try:
                file_ext = ".ISO"
                to_extract = next(file for file in file_list if file.upper().endswith(file_ext))
            except StopIteration:
                file_ext = ".IMG"
                to_extract = next(file for file in file_list if file.upper().endswith(file_ext))
            # Extract the file
            extract_file_from_zip(archive_path, to_extract, new_file.parent)
            extracted_file = new_file.parent / to_extract
        # Rename to the final destination
        try:
            os.replace(extracted_file, new_file.with_suffix(file_ext.lower()))
        except Exception as e:
            self.logging_callback(f"[{ISOname}] Error replacing file: {e}")
            return None
        # Cleanup
        archive_path.unlink(missing_ok=True)
        return True


    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = [
            "BonusCD",
            "FloppyEdition",
            "FullUSB",
            "LegacyCD",
            "LiteUSB",
            "LiveCD",
        ]
        self.edition = next(
            valid_ed
            for valid_ed in self.valid_editions
            if valid_ed.lower() == edition.lower()
        )
        # Set file extension based on edition (assume ISO for BonusCD/LiveCD/LegacyCD, IMG for USB editions)
        iso_editions = {"BonusCD", "LiveCD", "LegacyCD"}
        file_extension = "iso" if self.edition in iso_editions else "img"
        file_path = folder_path / FILE_NAME.replace("[[EXT]]", file_extension)
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=max(self.retries_count, 5), delay=2, logging_callback=self.logging_callback)
        if resp is None or getattr(resp, 'status_code', 200) != 200:
            self.download_page = None
            self.soup_download_page = None
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(self.download_page.content.decode("utf-8"), features="html.parser")


    @cache
    def _get_download_link(self) -> str | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            return None
        latest_version_str = self._version_to_str(latest_version).lstrip("/")
        return f"{DOWNLOAD_PAGE_URL}/{latest_version_str}/FD{''.join(latest_version)}-{self.edition}.zip"


    def check_integrity(self) -> bool | int | None:
        # FreeDOS only provides a hash for the zip archive, not the extracted ISO/IMG
        return None

    def _get_local_file(self) -> Path | None:
        file_path = self._get_normalized_file_path(
            absolute=True,
            version=None,
            edition=self.edition if self.has_edition() else None,  # type: ignore
            lang=self.lang if self.has_lang() else None,  # type: ignore
        )

        local_files = glob.glob(
            str(file_path.with_suffix(".*")).replace("[[VER]]", "*")
        )

        if local_files:
            return Path(local_files[0])
        self.logging_callback(f"[{ISOname}._get_local_file] No local file found for {self.__class__.__name__}")
        return None

    @cache
    def _get_latest_version(self) -> list[str] | None:
        if not self.soup_download_page:
            self.logging_callback(f"[{ISOname}] No download page available to parse version.")
            return None
        download_a_tags = self.soup_download_page.find_all("a", href=True)
        if not download_a_tags:
            self.logging_callback(f"[{ISOname}] Could not parse the download page for versions.")
            return None
        latest_version = self._get_local_version()
        version_regex = re.compile(r"^([0-9]+(\.[0-9]+)*)$")
        for a_tag in download_a_tags:
            href = a_tag.get("href")
            if href is None:
                continue
            version = str(href).rstrip("/")
            if version_regex.fullmatch(version):
                compared_version = self._str_to_version(version)
                if latest_version:
                    if self._compare_version_numbers(latest_version, compared_version):
                        latest_version = compared_version
                else:
                    latest_version = compared_version
        if not latest_version:
            self.logging_callback(f"[{ISOname}] Could not find a valid version on the download page.")
            return None
        return latest_version

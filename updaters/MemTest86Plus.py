from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.parse_hash import parse_hash
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.shared.unzip_file import unzip_file
from updaters.shared.robust_download import robust_download
from updaters.shared.robust_get import robust_get
from updaters.shared.fetch_hashes_from_url import fetch_hashes_from_url
import os

DOMAIN = "https://www.memtest.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}"
FILE_NAME = "Memtest86plus-[[VER]].iso"
ISOname = "MemTest86Plus"


class MemTest86Plus(GenericUpdater):
    """
    A class representing an updater for MemTest86+.

    Attributes:
        download_page (requests.Response): The HTTP response containing the download page HTML.
        soup_download_page (BeautifulSoup): The parsed HTML content of the download page.
        soup_download_card (Tag): The specific HTML Tag containing the download information card.

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, *args, **kwargs):
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        self.download_page = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        self.soup_download_page = None
        self.soup_download_card: Tag | None = None
        self.sha256sum_txt = None
        if self.download_page is not None:
            self.soup_download_page = BeautifulSoup(self.download_page.content.decode("utf-8"), features="html.parser")
            self.soup_download_card: Tag | None = self.soup_download_page.find("div", attrs={"class": "col-xxl-4"})  # type: ignore
            if not self.soup_download_card:
                if self.logging_callback:
                    self.logging_callback(f"[{ISOname}] ERROR: Could not find the card containing download information on {DOWNLOAD_PAGE_URL}")
                return
            latest_version = self._get_latest_version()
            if latest_version is not None:
                version_str = self._version_to_str(latest_version)
                sha_256_url = f"{DOWNLOAD_PAGE_URL}/download/v{version_str}/sha256sum.txt"
                try:
                    self.sha256sum_txt = fetch_hashes_from_url(sha_256_url)
                    if self.logging_callback:
                        self.logging_callback(f"[{ISOname}] Successfully fetched sha256sum.txt from {sha_256_url}")
                except Exception as e:
                    self.sha256sum_txt = None
                    if self.logging_callback:
                        self.logging_callback(f"[{ISOname}] ERROR: Failed to fetch sha256sum.txt from {sha_256_url}: {e}")
            else:
                if self.logging_callback:
                    self.logging_callback(f"[{ISOname}] ERROR: Could not determine latest version, skipping hash fetch.")
                self.sha256sum_txt = None

    @cache
    def _get_download_link(self) -> str | None:
        if not self.soup_download_card:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] ERROR: soup_download_card is None, cannot extract download link.")
            return None
        download_element: Tag | None = self.soup_download_card.find("a", string="Linux ISO (64 bits)")  # type: ignore
        if not download_element:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] ERROR: Could not find the download link for 'Linux ISO (64 bits)' in the download card.")
            return None
        link = download_element.get('href')
        if not link:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] ERROR: Download link element found but 'href' attribute is missing.")
            return None
        full_link = f"{DOWNLOAD_PAGE_URL}{link}"
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] Download link resolved: {full_link}")
        return full_link

    def check_integrity(self) -> bool | int:
        """
        Check the integrity of the downloaded archive (zip) if it exists.
        Returns:
            True if integrity check passes
            False if file not there or integrity check failed
            -1 if error fetching the hash online
        """
        new_file_path = self._get_complete_normalized_file_path(absolute=True)
        latest_version = self._get_latest_version()
        if not isinstance(latest_version, list):
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] ERROR: Could not determine latest version for integrity check.")
            return -1
        archive_path = new_file_path.parent / f"mt86plus_{self._version_to_str(latest_version)}_64.iso.zip"
        if not archive_path.exists():
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}.check_integrity] Archive does not exist: {archive_path}")
            return False
        # Archive exists, now check hash
        sha256_checksums_str = self.sha256sum_txt
        zip_filename = archive_path.name
        if not sha256_checksums_str:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] ERROR: No SHA256 checksum available for {zip_filename}, cannot verify integrity.")
            return -1
        sha256_checksum = parse_hash(sha256_checksums_str, [zip_filename], 0)
        if not sha256_checksum:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] ERROR: No SHA256 checksum found for {zip_filename} in hash file.")
            return -1
        if not sha256_hash_check(archive_path, sha256_checksum, package_name=ISOname, logging_callback=self.logging_callback):
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}.check_integrity] Archive hash check failed.")
            return False
        return True

    def install_latest_version(self) -> bool | None:
        """
        Download and install the latest version. Returns True on success, False on failure, or None if integrity cannot be verified.
        """
        download_link = self._get_download_link()
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] _get_download_link() returned: {download_link}")
        if not download_link:
            msg = f"[{ISOname}] ERROR: No valid download link found, aborting install."
            if self.logging_callback:
                self.logging_callback(msg)
            return None

        new_file_path = self._get_complete_normalized_file_path(absolute=True)
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] _get_complete_normalized_file_path(absolute=True) returned: {new_file_path}")
        if new_file_path is None:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] ERROR: Could not resolve normalized file path for install (got None).")
            return None
        if not isinstance(new_file_path, Path):
            new_file_path = Path(new_file_path)

        latest_version = self._get_latest_version()
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] _get_latest_version() returned: {latest_version}")
        if not isinstance(latest_version, list):
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] ERROR: Could not determine latest version for install.")
            return None
        archive_path = new_file_path.parent / f"mt86plus_{self._version_to_str(latest_version)}_64.iso.zip"
        self.logging_callback(f"[{ISOname}] Will download archive to: {archive_path}")
        # Always redownload the archive
        self.logging_callback(f"[{ISOname}] Downloading archive from {download_link} to {archive_path}")
        result = robust_download(download_link, archive_path, retries=self.retries_count, logging_callback=self.logging_callback, redirects=False)
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] robust_download result: {result}")
        if not result:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] ERROR: Download failed for {download_link}")
            return None
        # Centralized integrity check
        integrity_result = self.check_integrity()
        if integrity_result != True:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Integrity check failed after download. Result: {integrity_result}")
            return False
        self.logging_callback(f"[{ISOname}] Extracting archive {archive_path}")
        from updaters.shared.find_biggest_file_in_zip import find_biggest_file_in_zip
        to_extract = find_biggest_file_in_zip(str(archive_path), ext=".iso")
        if not to_extract:
            msg = f"[{ISOname}] ERROR: No .iso file found in archive."
            if self.logging_callback:
                self.logging_callback(msg)
            return None
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] Will extract: {to_extract}")
        import zipfile
        with zipfile.ZipFile(archive_path, 'r') as zf:
            zf.extract(to_extract, path=new_file_path.parent)
        # The output ISO should be named as the archive minus the .zip extension
        expected_iso_path = archive_path.with_suffix("")
        extracted_iso_path = new_file_path.parent / to_extract
        try:
            if extracted_iso_path.resolve() != expected_iso_path.resolve():
                os.replace(extracted_iso_path, expected_iso_path)
            self.logging_callback(f"[{ISOname}] Installed new version to {expected_iso_path}")
        except Exception as e:
            msg = f"[{ISOname}] ERROR: Error replacing file: {e}"
            if self.logging_callback:
                self.logging_callback(msg)
            return None
        # Leave the archive for future integrity checks
        return True
    
    @cache
    def _get_latest_version(self):
        card_title: Tag | None = None
        if self.soup_download_card:
            card_title = self.soup_download_card.find(
                "span", attrs={"class": "text-primary fs-2"}
            )  # type: ignore

        if not card_title:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not find the latest version")
            return None

        # Return a tuple/list of version parts (e.g., ["7", "00"])
        version_str = card_title.getText().split("v")[-1].strip()
        return version_str.split('.')

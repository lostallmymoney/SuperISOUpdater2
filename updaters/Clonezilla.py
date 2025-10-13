from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag
from functools import cache
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.shared.parse_hash import parse_hash
from updaters.shared.verify_file_size import verify_file_size

DOMAIN = "https://clonezilla.org"
FILE_NAME = "clonezilla-live-[[VER]]-amd64.iso"
ISOname = "Clonezilla"


class Clonezilla(GenericUpdater):
    """
    A class representing an updater for Clonezilla.

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, *args, **kwargs):
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)

    @cache
    def _get_download_link(self) -> str | None:
        latest_version = self._get_latest_version()
        if not isinstance(latest_version, list):
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] _get_download_link: latest_version is not list, got {type(latest_version).__name__}: {latest_version}")
            return None
        ver = self._version_to_str(latest_version)
        repo = "https://downloads.sourceforge.net"
        return f"{repo}/clonezilla/clonezilla-live-{Clonezilla._get_clonezilla_version_style(ver)}-amd64.iso"

    def check_integrity(self) -> bool | int | None:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if not isinstance(local_file, Path):
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] check_integrity: local_file is not Path")
            return -1
        if not isinstance(download_link, str):
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] check_integrity: download_link is not str")
            return -1
        # First, verify file size
        if not verify_file_size(local_file, download_link, package_name=ISOname, logging_callback=self.logging_callback):
            return False
        # Fetch and process the checksum page as in the original SISOU logic
        resp = robust_get(f"{DOMAIN}/downloads/stable/checksums-contents.php", retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] check_integrity: Failed to fetch checksums page: HTTP {getattr(resp, 'status_code', 'No Response')}")
            return -1
        soup = BeautifulSoup(resp.content.decode("utf-8"), features="html.parser")
        pre: Tag | None = soup.find("pre")  # type: ignore
        if not pre:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] check_integrity: Unable to extract <pre> elements from checksum; skipping integrity check.")
            return -1
        checksums = pre.text.split("###")
        sha256_sums = next((c for c in checksums if "SHA256SUMS" in c), None)
        if not sha256_sums:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] check_integrity: Could not find SHA256 sum; skipping integrity check.")
            return -1
        hash_val = parse_hash(sha256_sums, ["amd64.iso"], 0, logging_callback=self.logging_callback)
        if not hash_val:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] check_integrity: Could not parse SHA256 hash; skipping integrity check.")
            return -1
        # Now check the hash
        return sha256_hash_check(local_file, hash_val, package_name=ISOname, logging_callback=self.logging_callback)

    @cache
    def _get_latest_version(self) -> list[str] | None:
        resp = robust_get(f"{DOMAIN}/downloads/stable/changelog-contents.php", retries=self.retries_count,
            delay=1, logging_callback=self.logging_callback)
        if resp is None:
            return None
        soup = BeautifulSoup(resp.content.decode("utf-8"), features="html.parser")
        first_paragraph: Tag | None = soup.find("p")  # type: ignore
        if not first_paragraph:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Unable to extract <p> elements from changelog")
            return None
        version_raw = first_paragraph.getText().split()[-1]
        # Only keep numeric and dot components for version comparison
        version_clean = version_raw.replace("-", ".")
        version_parts = [part for part in version_clean.split(".") if part.isdigit()]
        return version_parts

    @staticmethod
    def _get_clonezilla_version_style(version: str):
        """
        Convert the version string from "x.y.z" to "x.y-z" format, as used by Clonezilla.

        Parameters:
            version (str): The version string in "x.y.z.a" format.

        Returns:
            str: The version string in "x.y.z-a" format.
        """
        return "-".join(version.rsplit(".", 1))

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
                self.logging_callback(f"ERROR: Could not find the card containing download information on {DOWNLOAD_PAGE_URL}")
                return
            latest_version = self._get_latest_version()
            if latest_version is not None:
                version_str = self._version_to_str(latest_version)
                sha_256_url = f"{DOWNLOAD_PAGE_URL}/download/v{version_str}/sha256sum.txt"
                try:
                    self.sha256sum_txt = fetch_hashes_from_url(sha_256_url, self.logging_callback)
                    self.logging_callback(f"Successfully fetched sha256sum.txt from {sha_256_url}")
                except Exception as e:
                    self.sha256sum_txt = None
                    self.logging_callback(f"ERROR: Failed to fetch sha256sum.txt from {sha_256_url}: {e}")
            else:
                self.logging_callback(f"ERROR: Could not determine latest version, skipping hash fetch.")
                self.sha256sum_txt = None

    @cache
    def _get_download_link(self) -> str | None:
        if not self.soup_download_card:
            self.logging_callback(f"ERROR: soup_download_card is None, cannot extract download link.")
            return None
        download_element: Tag | None = self.soup_download_card.find("a", string="Linux ISO (64 bits)")  # type: ignore
        if not download_element:
            self.logging_callback(f"ERROR: Could not find the download link for 'Linux ISO (64 bits)' in the download card.")
            return None
        link = download_element.get('href')
        if not link:
            self.logging_callback(f"ERROR: Download link element found but 'href' attribute is missing.")
            return None
        full_link = f"{DOWNLOAD_PAGE_URL}{link}"
        self.logging_callback(f"Download link resolved: {full_link}")
        return full_link

    def check_integrity(self) -> bool | int | None:
        """
        Check the integrity of the downloaded zip and extracted ISO file.
        Returns True if both are valid, False if not, -1 on error, None if file missing.
        """
        latest_version = self._get_latest_version()
        if not isinstance(latest_version, list):
            self.logging_callback(f"check_integrity: Could not determine latest version.")
            return -1
        new_file_path = self._get_complete_normalized_file_path(absolute=True)
        if not new_file_path:
            self.logging_callback(f"check_integrity: Could not resolve normalized file path.")
            return -1
        if not isinstance(new_file_path, Path):
            new_file_path = Path(new_file_path)
        archive_path = new_file_path.parent / f"mt86plus_{self._version_to_str(latest_version)}_64.iso.zip"
        if not archive_path.exists():
            self.logging_callback(f"check_integrity: Zip file does not exist: {archive_path}")
            return None
        # Check hash
        sha256_checksums_str = self.sha256sum_txt
        zip_filename = archive_path.name
        sha256_checksum = parse_hash(sha256_checksums_str, [zip_filename], 0, self.logging_callback) if sha256_checksums_str else None
        if not sha256_checksum:
            self.logging_callback(f"check_integrity: No SHA256 checksum available for {zip_filename}.")
            return -1
        hash_ok = sha256_hash_check(archive_path, sha256_checksum, logging_callback=self.logging_callback)
        if not hash_ok:
            self.logging_callback(f"check_integrity: Zip archive hash check failed.")
            return False
        # Check ISO file exists
        if not new_file_path.exists():
            self.logging_callback(f"check_integrity: ISO file does not exist: {new_file_path}")
            return None
        self.logging_callback(f"check_integrity: Both zip and ISO file passed integrity check.")
        return True

    def install_latest_version(self) -> bool | None:
        """
        Download and install the latest version. Returns True on success, False on failure, or None if integrity cannot be verified.
        """
        download_link = self._get_download_link()
        self.logging_callback(f"_get_download_link() returned: {download_link}")
        if not download_link:
            self.logging_callback("ERROR: No valid download link found, aborting install.")
            return None

        new_file_path = self._get_complete_normalized_file_path(absolute=True)
        self.logging_callback(f"_get_complete_normalized_file_path(absolute=True) returned: {new_file_path}")
        if new_file_path is None:
            self.logging_callback("ERROR: Could not resolve normalized file path for install (got None).")
            return None
        if not isinstance(new_file_path, Path):
            new_file_path = Path(new_file_path)

        latest_version = self._get_latest_version()
        self.logging_callback(f"_get_latest_version() returned: {latest_version}")
        if not isinstance(latest_version, list):
            self.logging_callback("ERROR: Could not determine latest version for install.")
            return None
        archive_path = new_file_path.parent / f"mt86plus_{self._version_to_str(latest_version)}_64.iso.zip"
        self.logging_callback(f"Will download archive to: {archive_path}")
        # Always redownload the archive
        self.logging_callback(f"Downloading archive from {download_link} to {archive_path}")
        result = robust_download(download_link, archive_path, retries=self.retries_count, logging_callback=self.logging_callback, redirects=False)
        self.logging_callback(f"robust_download result: {result}")
        if not result:
            self.logging_callback(f"ERROR: Download failed for {download_link}")
            return None
        # Check integrity before extraction
        integrity = self.check_integrity()
        if integrity == -1:
            self.logging_callback("ERROR: Integrity check encountered an error before extraction.")
            return None
        elif integrity is None:
            self.logging_callback("ERROR: Integrity check could not be completed before extraction (file missing).")
            return None
        elif integrity is False:
            self.logging_callback("ERROR: Integrity check failed before extraction.")
            return False
        elif integrity is True:
            self.logging_callback("Integrity check passed before extraction.")

        self.logging_callback(f"Extracting archive {archive_path}")
        unzip_file(archive_path, new_file_path.parent)
        iso = next((file for file in new_file_path.parent.glob("*.iso")), None)
        self.logging_callback(f"Found ISO after extraction: {iso}")
        if not iso:
            self.logging_callback("ERROR: No .iso file found in archive after extraction.")
            return None
        self.logging_callback(f"Extracted {iso} from archive.")
        # Do not delete the archive; keep it for future integrity checks
        try:
            if iso.resolve() != new_file_path.resolve():
                os.replace(iso, new_file_path)
            self.logging_callback(f"Installed new version to {new_file_path}")
        except Exception as e:
            self.logging_callback(f"ERROR: Error replacing file: {e}")
            return None
        return True
    
    @cache
    def _get_latest_version(self):
        card_title: Tag | None = None
        if self.soup_download_card:
            card_title = self.soup_download_card.find(
                "span", attrs={"class": "text-primary fs-2"}
            )  # type: ignore

        if not card_title:
            self.logging_callback(f"Could not find the latest version")
            return None

        # Return a tuple/list of version parts (e.g., ["7", "00"])
        version_str = card_title.getText().split("v")[-1].strip()
        return version_str.split('.')

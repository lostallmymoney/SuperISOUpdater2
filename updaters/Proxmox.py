from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.parse_hash import parse_hash
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.shared.robust_get import robust_get
from updaters.shared.check_remote_integrity import check_remote_integrity
from updaters.shared.verify_file_size import verify_file_size

DOMAIN = "https://enterprise.proxmox.com"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/iso"
FILE_NAME = "proxmox-[[EDITION]]_[[VER]].iso"
ISOname = "Proxmox"




class Proxmox(GenericUpdater):
    """
    A class representing an updater for Proxmox.

    Attributes:
        valid_editions (list[str]): List of valid editions to use
        edition (str): Edition to download
        download_page (requests.Response): The HTTP response containing the download page HTML.
        soup_download_page (BeautifulSoup): The parsed HTML content of the download page.

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, edition: str, logging_callback=None) -> None:
        self.valid_editions = [
            "ve",
            "mail-gateway",
            "backup-server",
        ]
        self.edition = edition
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, logging_callback=logging_callback)

        # Make the parameter case insensitive, and find back the correct case using valid_editions
        self.edition = next(
            valid_ed
            for valid_ed in self.valid_editions
            if valid_ed.lower() == self.edition.lower()
        )

        resp = robust_get(DOWNLOAD_PAGE_URL, retries=3, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.soup_download_page = None
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(
            self.download_page.content.decode("utf-8"), features="html.parser"
        )

    @cache
    def _get_download_link(self) -> str | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            return None
        latest_version_str = self._version_to_str(latest_version)
        return f"{DOWNLOAD_PAGE_URL}/{FILE_NAME.replace('[[VER]]', latest_version_str).replace('[[EDITION]]', self.edition)}"

    @cache
    def _get_latest_version(self) -> list[str] | None:
        def parse_version(href: str) -> list[str]:
            return self._str_to_version(href.split('_')[1].split('.iso')[0])

        if not self.soup_download_page:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not parse the download page (no soup)")
            return None
        downloads_list: Tag | None = self.soup_download_page.find("pre")  # type: ignore
        if not downloads_list:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not parse the download page")
            return None

        download_items = downloads_list.find_all("a")
        if not download_items:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not parse the list of download links")
            return None

        download_links: list[str] = []
        for download_link in download_items:
            href = download_link.get("href")
            if href is not None and isinstance(href, str) and self.edition in href:
                download_links.append(href)
        if not download_links:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not find links for this edition")
            return None

        latest_version = []
        for link in download_links:
            version = parse_version(link)
            is_greater_version = self._compare_version_numbers(latest_version, version)
            if is_greater_version:
                latest_version = version

        return latest_version

    def check_integrity(self) -> bool | None:
        sha256_url = f"{DOWNLOAD_PAGE_URL}/SHA256SUMS"
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        # Ensure local_file is a Path before passing to verify_file_size
        if not isinstance(local_file, Path) or download_link is None:
            return False
        if verify_file_size(local_file, download_link, package_name=ISOname, logging_callback=self.logging_callback) is False:
            return False
        return check_remote_integrity(
            hash_url=sha256_url,
            local_file=local_file,
            hash_type="sha256",
            parse_hash_args=([str(self._get_complete_normalized_file_path(absolute=False))], 0),
            logging_callback=self.logging_callback,
        )

    def _version_to_str(self, version: list[str], version_splitter: str = ".") -> str:
        version = version.copy()
        dash_something: str = version.pop()
        return f"{version_splitter.join(str(i) for i in version)}-{dash_something}"

    def _str_to_version(self, version_str: str) -> list[str]:
        version: list[str] = [
            version_number.strip()
            for version_number in version_str.split('.')
        ]
        dash_something: list[str] = version.pop().split("-")
        return version + dash_something


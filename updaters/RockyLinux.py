from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.check_remote_integrity import check_remote_integrity

DOMAIN = "https://download.rockylinux.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/pub/rocky"
FILE_NAME = "Rocky-[[VER]]-x86_64-[[EDITION]].iso"
ISOname = "RockyLinux"


class RockyLinux(GenericUpdater):
    """
    A class representing an updater for Rocky Linux.

    Attributes:
        valid_editions (list[str]): List of valid editions to use
        edition (str): Edition to download
        download_page (requests.Response): The HTTP response containing the download page HTML.
        soup_download_page (BeautifulSoup): The parsed HTML content of the download page.

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["dvd", "boot", "minimal"]
        self.edition = edition.lower()
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
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
        file_path = self._get_complete_normalized_file_path(
            absolute=False,
            latest=True
        )
        return f"{DOWNLOAD_PAGE_URL}/{latest_version_str}/isos/x86_64/{file_path}"

    def check_integrity(self) -> bool | int | None:
        sha256_url = f"{self._get_download_link()}.CHECKSUM"
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if download_link is None:
            self.logging_callback("Could not resolve download link for integrity check.")
            return -1
        if not local_file.exists():
            self.logging_callback("Local file does not exist for integrity check.")
            return None
        if verify_file_size(local_file, download_link, logging_callback=self.logging_callback) is False:
            return False
        return check_remote_integrity(
            hash_url=sha256_url,
            local_file=local_file,
            hash_type="sha256",
            parse_hash_args=([str(self._get_complete_normalized_file_path(absolute=False)), "="], -1),
            logging_callback=self.logging_callback,
        )
    @cache
    def _get_latest_version(self) -> list[str] | None:
        if self.soup_download_page is None:
            return None
        download_a_tags = self.soup_download_page.find_all("a", href=True)
        if not download_a_tags:
            self.logging_callback("Could not parse the download page for versions.")
            return None

        local_version = self._get_local_version()
        latest = local_version or []

        for a_tag in download_a_tags:
            href = a_tag.get("href")
            if not href or not href[0].isnumeric():
                continue
            version_candidate = href[:-1]
            if isinstance(version_candidate, str):
                version_number = self._str_to_version(version_candidate)
                if self._compare_version_numbers(latest, version_number):
                    latest = version_number

        return latest
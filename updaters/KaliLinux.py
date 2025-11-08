from functools import cache
from pathlib import Path
from urllib.parse import urljoin
import re
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get

from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.check_remote_integrity import check_remote_integrity

DOMAIN = "https://cdimage.kali.org"
DOWNLOAD_PAGE_URL = urljoin(DOMAIN, "current/")
FILE_NAME = "kali-linux-[[VER]]-[[EDITION]]-amd64.iso"
ISOname = "KaliLinux"



class KaliLinux(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = [
            "installer",
            "installer-netinst",
            "installer-purple",
            "live",
        ]
        self.edition = edition.lower()
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.html_content = None
            return
        self.download_page = resp
        self.html_content = self.download_page.text

    @cache
    def _get_download_link(self) -> str | None:
        return urljoin(
            DOWNLOAD_PAGE_URL,
            str(self._get_complete_normalized_file_path(absolute=False)),
        )


    def check_integrity(self, *args, **kwargs) -> bool | int | None:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(local_file, Path):
            self.logging_callback(f"Invalid local file path: {local_file}")
            return -1
        iso_url = self._get_download_link()
        if iso_url is None:
            return -1
        # First, verify file size
        if not verify_file_size(local_file, iso_url, logging_callback=self.logging_callback):
            return False
        # Then, check remote integrity (hash)
        sha256_url = urljoin(DOWNLOAD_PAGE_URL, "SHA256SUMS")
        match_strings = [str(self._get_complete_normalized_file_path(absolute=False))]
        return check_remote_integrity(
            sha256_url,
            local_file,
            "sha256",
            (match_strings, 0),
            logging_callback=self.logging_callback
        )


    @cache
    def _get_latest_version(self) -> list[str] | None:
        if not self.html_content:
            self.logging_callback(f"No HTML content to parse for version.")
            return None
        # Use regex to find all hrefs in <a> tags
        hrefs = re.findall(r'<a[^>]+href=["\']([^"\'>]+)["\']', self.html_content)
        if not hrefs:
            self.logging_callback(f"Could not parse the download page for version.")
            return None
        # Try to find the first href that matches the expected ISO pattern
        pattern = re.compile(r'kali-linux-(.+?)-' + re.escape(self.edition) + r'-amd64\.iso')
        for href in hrefs:
            if pattern.search(href):
                # Extract version from the filename
                parts = href.split("-")
                if len(parts) >= 3:
                    return self._str_to_version(parts[2])
        self.logging_callback(f"Could not determine the latest version string.")
        return None

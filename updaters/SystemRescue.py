

from functools import cache
import re
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.check_remote_integrity import check_remote_integrity
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size

DOMAIN = "https://www.system-rescue.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/Download"
FILE_NAME = "systemrescue-[[VER]]-amd64.iso"
ISOname = "SystemRescue"

class SystemRescue(GenericUpdater):
    """
    A class representing an updater for SystemRescue.
    """
    def __init__(self, folder_path: Path, *args, **kwargs):
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.soup_download_page = None
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(self.download_page.content.decode("utf-8"), features="html.parser")

    @cache
    def _get_download_link(self) -> str | None:
        download_tag: Tag | None = self._find_in_table("Fastly")
        if not download_tag:
            self.logging_callback("Failed to find the `Tag` containing the download link")
            return None
        href_attributes = download_tag.find_all(href=True)
        if not href_attributes:
            self.logging_callback("No download link found in the `Tag`")
            return None
        href = href_attributes[0].get("href")
        if not isinstance(href, str):
            self.logging_callback("Download link is not a string")
            return None
        return href

    def check_integrity(self) -> bool | int | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            return -1
        version_str = self._version_to_str(latest_version)
        sha256_download_link = f"{DOMAIN}/releases/{version_str}/systemrescue-{version_str}-amd64.iso.sha256"
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if not isinstance(local_file, Path) or not isinstance(download_link, str):
            return -1
        if verify_file_size(local_file, download_link, logging_callback=self.logging_callback) is False:
            return False
        return check_remote_integrity(
            hash_url=sha256_download_link,
            local_file=local_file,
            hash_type="sha256",
            parse_hash_args=([f"systemrescue-{version_str}-amd64.iso"], 0),
            logging_callback=self.logging_callback,
        )

    @cache
    def _get_latest_version(self) -> list[str] | None:
        download_link = self._get_download_link()
        if not download_link:
            self.logging_callback("Could not get download link for version extraction.")
            return None
        latest_version_regex = re.search(
            r"releases\/(.+)\/",  # Parse from https://fastly-cdn.system-rescue.org/releases/10.01/systemrescue-10.01-amd64.iso
            download_link,
        )
        if latest_version_regex:
            return self._str_to_version(latest_version_regex.group(1))
        self.logging_callback("Could not find the latest available version in download link.")
        return None

    def _find_in_table(self, row_name_contains: str) -> Tag | None:
        s: Tag | None = self.soup_download_page.find("div", attrs={"id": "colcenter"}) if self.soup_download_page else None  # type: ignore
        if not s:
            self.logging_callback("Could not find the div containing the table with download information.")
            return None
        s = s.find("table")  # type: ignore
        if not s:
            self.logging_callback("Could not find the table containing download information.")
            return None
        for tr in s.find_all("tr"):
            for td in tr.find_all("td"):
                if row_name_contains in td.getText():
                    return td
        self.logging_callback(f"Failed to find '{row_name_contains}' in the table.")
        return None

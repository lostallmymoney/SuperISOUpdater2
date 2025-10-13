
from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.check_remote_integrity import check_remote_integrity
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size

DOMAIN = "https://releases.ubuntu.com"
DOWNLOAD_PAGE_URL = f"{DOMAIN}"
FILE_NAME = "ubuntu-[[EDITION]]-[[VER]]-desktop-amd64.iso"
ISOname = "Ubuntu"


class Ubuntu(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["LTS", "Interim"]
        self.edition = next(
            valid_ed
            for valid_ed in self.valid_editions
            if valid_ed.lower() == edition.lower()
        )
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
        latest_version = self._get_latest_version()
        if latest_version is None:
            return None
        latest_version_str = self._version_to_str(latest_version)
        return f"{DOMAIN}/{latest_version_str}/ubuntu-{latest_version_str}-desktop-amd64.iso"


    def check_integrity(self) -> bool | int | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            return None
        latest_version_str = self._version_to_str(latest_version)
        sha256_url = f"{DOWNLOAD_PAGE_URL}/{latest_version_str}/SHA256SUMS"
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if not isinstance(local_file, Path) or download_link is None:
            return -1
        if verify_file_size(local_file, download_link, package_name=ISOname, logging_callback=self.logging_callback) is False:
            return False
        return check_remote_integrity(
            hash_url=sha256_url,
            local_file=local_file,
            hash_type="sha256",
            parse_hash_args=([f"ubuntu-{latest_version_str}-desktop-amd64.iso"], 0),
            logging_callback=self.logging_callback
        )


    @cache
    def _get_latest_version(self) -> list[str] | None:
        download_categories = self.soup_download_page.find_all("div", attrs={"class": "col-4"}) if self.soup_download_page else []
        if not download_categories:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] We were not able to parse the download categories.")
            return None
        downloads = next(
            (download_category for download_category in download_categories if (h4 := download_category.find("h4")) and h4.text == f"{self.edition} Releases"),
            None
        )
        if not downloads:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] We were not able to parse the {self.edition} downloads.")
            return None
        latest = downloads.find("a", href=True)
        if not latest:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] We were not able to find {self.edition} downloads.")
            return None
        xy_version = latest.getText().split()[1]
        resp = robust_get(f"{DOWNLOAD_PAGE_URL}/{xy_version}", retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Failed to fetch version page from '{DOWNLOAD_PAGE_URL}/{xy_version}'")
            return None
        soup_version_page = BeautifulSoup(resp.content.decode("utf-8"), features="html.parser")
        title = soup_version_page.find("title")
        if not title:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] We were not able to find the title of the version page.")
            return None
        title_text = title.getText()
        return self._str_to_version(title_text.split()[1])

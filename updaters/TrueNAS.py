
from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.check_remote_integrity import check_remote_integrity

DOMAIN = "https://www.truenas.com"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/download-truenas-[[EDITION]]"
FILE_NAME = "TrueNAS-[[EDITION]]-[[VER]].iso"
ISOname = "TrueNAS"



class TrueNAS(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["core", "scale"]
        self.edition = edition.lower()
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        self.download_page_url = DOWNLOAD_PAGE_URL.replace("[[EDITION]]", self.edition)
        resp = robust_get(self.download_page_url, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.soup_download_page = None
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(self.download_page.content.decode("utf-8"), features="html.parser")


    @cache
    def _get_download_link(self) -> str | None:
        if self.soup_download_page is None:
            return None
        a_tag = self.soup_download_page.find("a", attrs={"id": "downloadTrueNAS"})
        if not a_tag:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not find HTML tag containing download URL")
            return ""
        return a_tag["href"]  # type: ignore

    def check_integrity(self) -> bool | None:
        download_link = self._get_download_link()
        sha256_url = f"{download_link}.sha256"
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(local_file, Path) or not isinstance(download_link, str):
            return None
        if verify_file_size(local_file, download_link, package_name=ISOname, logging_callback=self.logging_callback) is False:
            return False
        # Use check_remote_integrity for hash check
        # For TrueNAS, the .sha256 file contains only the hash, no filename
        return check_remote_integrity(
            sha256_url,
            local_file,
            "sha256",
            ([], 0),
            logging_callback=self.logging_callback
        )

    @cache
    def _get_latest_version(self) -> list[str] | None:
        download_link = self._get_download_link()
        if not download_link or "-" not in download_link:
            return None
        version = download_link.split("-")[-1]
        return self._str_to_version(version.replace(".iso", ""))

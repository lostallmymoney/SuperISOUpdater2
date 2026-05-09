
from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.check_remote_integrity import check_remote_integrity

DOMAIN = "https://mirrors.edge.kernel.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/linuxmint/stable/"
FILE_NAME = "linuxmint-[[VER]]-[[EDITION]]-64bit.iso"
ISOname = "LinuxMint"



class LinuxMint(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["cinnamon", "mate", "xfce"]
        self.edition = edition.lower()
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.soup_download_page = None
            self.sha256sum_txt = None
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(self.download_page.content.decode("utf-8"), features="html.parser")

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
        return f"{DOWNLOAD_PAGE_URL}/{latest_version_str}/{file_path}"


    def check_integrity(self, *args, **kwargs) -> bool:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(local_file, Path):
            if not hasattr(self, "file_path") and not isinstance(self.file_path, Path):
                local_file = self.file_path
                return False
            else:
                return False
        download_link = self._get_download_link()
        if download_link is None:
            return False
        # First, verify file size
        if not verify_file_size(local_file, download_link, logging_callback=self.logging_callback):
            return False
        # Then, check remote integrity (hash)
        latest_version = self._get_latest_version()
        if latest_version is None:
            return False
        latest_version_str = self._version_to_str(latest_version)
        sha256_url = f"https://mirrors.edge.kernel.org/linuxmint/stable/{latest_version_str}/sha256sum.txt"
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
        if self.soup_download_page is None:
            self.logging_callback(f"Download page soup is None, cannot parse download links.")
            return None
        download_a_tags = list(self.soup_download_page.find_all("a", href=True))
        local_version = self._get_local_version()
        latest = local_version or []
        for a_tag in download_a_tags:
            href = a_tag.get("href")
            if not href or not isinstance(href, str) or not href or not href[0].isnumeric():
                continue
            version_number = self._str_to_version(href[:-1]) if isinstance(href, str) else []
            if self._compare_version_numbers(latest, version_number):
                latest = version_number
        return latest if latest else []


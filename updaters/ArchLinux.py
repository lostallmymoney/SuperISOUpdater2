from bs4 import BeautifulSoup
from pathlib import Path
from functools import cache
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.check_remote_integrity import check_remote_integrity

DOMAIN = "https://geo.mirror.pkgbuild.com"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/iso/latest"
FILE_NAME = "archlinux-[[VER]]-x86_64.iso"
ISOname = "ArchLinux"

class ArchLinux(GenericUpdater):
    def __init__(self, folder_path: Path, *args, **kwargs):
        self.folder_path = Path(folder_path)
        self.file_name = FILE_NAME
        file_path = self.folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None:
            self.soup_download_page = None
            return
        self.soup_download_page = BeautifulSoup(resp.content.decode('utf-8'), features="html.parser")

    @cache
    def _get_latest_version(self) -> list[str] | None:
        if not self.soup_download_page:
            return None
        download_a_tags = self.soup_download_page.find_all("a", href=True)
        for a_tag in download_a_tags:
            href = a_tag.get("href")
            if href and "archlinux" in href:
                return self._str_to_version(a_tag.getText().split("-")[1])
        self.logging_callback("Could not parse latest version from download page")
        return None

    @cache
    def _get_download_link(self) -> str | None:
        version = self._get_latest_version()
        if not version:
            return ""
        return f"{DOWNLOAD_PAGE_URL}/{FILE_NAME.replace('[[VER]]', self._version_to_str(version))}"

    def check_integrity(self) -> bool | int | None:
        version = self._get_latest_version()
        if not version:
            self.logging_callback("No version info for integrity check.")
            return -1
        file_path = self.folder_path / FILE_NAME.replace("[[VER]]", self._version_to_str(version))
        return check_remote_integrity(
            f"{DOWNLOAD_PAGE_URL}/sha256sums.txt",
            file_path,
            "sha256",
            parse_hash_args=([file_path.name], 0),
            logging_callback=self.logging_callback
        )

    def install_latest_version(self) -> None | bool:
        version = self._get_latest_version()
        if not version:
            return False
        # For ArchLinux, we don't have an 'old_file' concept, so pass None
        return super().install_latest_version()

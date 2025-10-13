from functools import cache
from pathlib import Path
import re
import requests
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.check_remote_integrity import check_remote_integrity
from updaters.shared.verify_file_size import verify_file_size

DOMAIN = "https://download.opensuse.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/download/tumbleweed/iso"
FILE_NAME = "openSUSE-[[EDITION]]-x86_64-[[VER]].iso"

ISOname = "OpenSUSERolling"


class OpenSUSERolling(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["MicroOS-DVD", "Tumbleweed-DVD", "Tumbleweed-NET", "Tumbleweed-GNOME-Live", "Tumbleweed-KDE-Live", "Tumbleweed-XFCE-Live", "Tumbleweed-Rescue-CD"]
        self.edition = edition
        self.download_page_url = DOWNLOAD_PAGE_URL
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)

    def _capitalize_edition(self) -> str:
        for capEdition in self.valid_editions:
            if capEdition.lower() is self.edition.lower():
                return capEdition
        # shouldn't get here
        return self.edition

    @cache
    def _get_download_link(self) -> str | None:
        isoFile = FILE_NAME.replace("[[EDITION]]", self._capitalize_edition()).replace("[[VER]]","Current")
        return f"{self.download_page_url}/{isoFile}"


    def check_integrity(self) -> bool | int | None:
        sha256_url = f"{self._get_download_link()}.sha256"
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
            parse_hash_args=([], 0),
            logging_callback=self.logging_callback
        )

    @cache
    def _get_latest_version(self) -> list[str] | None:
        sha256_url = f"{self._get_download_link()}.sha256"
        resp = requests.get(sha256_url)
        if resp.status_code != 200:
            return None
        sha256_sums = resp.text
        return self._str_to_version(sha256_sums.split(" ")[-1])

    def _str_to_version(self, version_str: str):
        version = "0"
        pattern = r'^.*Snapshot(\d*)-.*$'

        match = re.search(pattern, version_str)
        if match:
            version = match.group(1)
        return [version]

    def _version_to_str(self, version, version_splitter: str = "."):
        return f"Snapshot{version[0]}-Media"

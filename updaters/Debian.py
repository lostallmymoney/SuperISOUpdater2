from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.robust_get import robust_get
from updaters.shared.check_remote_integrity import check_remote_integrity


DOMAIN = "https://cdimage.debian.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/debian-cd/current-live/amd64/iso-hybrid/"
FILE_NAME = "debian-live-[[VER]]-amd64-[[EDITION]].iso"
ISOname = "Debian"


class Debian(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = [
            "cinnamon", "gnome", "kde", "lxde", "lxqt", "mate", "standard", "xfce"
        ]
        self.edition = edition.lower()
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)

        resp = robust_get(DOWNLOAD_PAGE_URL, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.soup_download_page = None
            self.soup_index_list = None
            self.logging_callback(f"ERROR: Could not fetch Debian download page at {DOWNLOAD_PAGE_URL}")
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(self.download_page.content.decode("utf-8"), features="html.parser")
        self.soup_index_list: Tag | None = self.soup_download_page.find("table", attrs={"id": "indexlist"})  # type: ignore
        if not self.soup_index_list:
            self.soup_index_list = None
            self.logging_callback(f"ERROR: Could not find index list table on Debian download page.")

    @cache
    def _get_download_link(self) -> str | None:
        return f"{DOWNLOAD_PAGE_URL}/{self._get_complete_normalized_file_path(absolute=False)}"

    def check_integrity(self) -> bool | None | int:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(local_file, Path):
            return -1
        download_link = self._get_download_link()
        if(download_link is None):
            return -1
        # First, verify file size (logging handled inside utility)
        if not verify_file_size(local_file, download_link, logging_callback=self.logging_callback):
            return False
        # Then, use shared check_remote_integrity for hash check
        sha256_url = f"{DOWNLOAD_PAGE_URL}SHA256SUMS"
        return check_remote_integrity(
            hash_url=sha256_url,
            local_file=local_file,
            hash_type="sha256",
            parse_hash_args=([str(self._get_complete_normalized_file_path(absolute=False))], 0),
            logging_callback=self.logging_callback,
            # removed isoname
        )

    @cache
    def _get_latest_version(self) -> list[str] | None:
        if not self.soup_index_list:
            self.logging_callback(f"Could not parse the download page (no index list)")
            return None
        download_a_tags = self.soup_index_list.find_all("a", href=True)
        if not download_a_tags:
            self.logging_callback(f"Could not parse the download page (no links)")
            return None
        match_str = str(self._get_normalized_file_path(absolute=False, version=None, edition=self.edition if self.has_edition() else None, lang=getattr(self, 'lang', None) if self.has_lang() else None)).split("[[VER]]")[-1]
        latest = next(
            (href for a_tag in download_a_tags if (href := a_tag.get("href")) and isinstance(href, str) and match_str in href),
            None
        )
        if latest and isinstance(latest, str) and "-" in latest:
            return self._str_to_version(latest.split("-")[2])
        else:
            self.logging_callback(f"Could not determine the latest version string.")
            return None


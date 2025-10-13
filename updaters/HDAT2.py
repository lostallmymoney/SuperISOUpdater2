

from functools import cache
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from bs4.element import Tag
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.parse_hash import parse_hash
from updaters.shared.md5_hash_check import md5_hash_check

DOMAIN = "https://www.hdat2.com"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/download.html"
FILE_NAME = "HDAT2_[[EDITION]]_[[VER]].[[EXT]]"
ISOname = "HDAT2"



class HDAT2(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["full", "lite", "diskette"]
        self.edition = edition.lower()
        extension = "IMG" if self.edition == "diskette" else "ISO"
        self.file_name = FILE_NAME.replace("[[EXT]]", extension)
        file_path = folder_path / self.file_name
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
        version_str = self._version_to_str(latest_version)
        soup = None
        if self.edition == "full":
            soup = self._find_in_table([version_str], ["LITE", "IMG", "EXE"])
        elif self.edition == "lite":
            soup = self._find_in_table([version_str, "LITE"], ["IMG", "EXE"])
        elif self.edition == "diskette":
            soup = self._find_in_table([version_str, "HDAT2IMG"], ["ISO", "EXE"])
        else:
            self.logging_callback(f"[{ISOname}] Edition {self.edition} is not implemented yet.")
            return None
        if not soup:
            self.logging_callback(f"[{ISOname}] Could not find table row for edition {self.edition} and version {version_str}.")
            return None
        a_tag = soup.find("a", href=True)
        if not a_tag:
            self.logging_callback(f"[{ISOname}] Could not find HTML tag containing download link.")
            return None
        return urljoin(DOMAIN, a_tag["href"])  # type: ignore

    def check_integrity(self) -> bool | int | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            return None
        version_str = self._version_to_str(latest_version)
        soup = None
        if self.edition == "full":
            soup = self._find_in_table([version_str], ["LITE"])
        elif self.edition == "lite":
            soup = self._find_in_table([version_str, "LITE"])
        elif self.edition == "diskette":
            soup = self._find_in_table([version_str, "HDAT2IMG"])
        else:
            self.logging_callback(f"[{ISOname}] Edition {self.edition} is not implemented yet.")
            return -1
        if not soup:
            self.logging_callback(f"[{ISOname}] Could not find table row for edition {self.edition} and version {version_str}.")
            return -1
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if download_link is None or not isinstance(local_file, Path):
            return -1
        if not verify_file_size(local_file, download_link, package_name=ISOname, logging_callback=self.logging_callback):
            return False
        tag_with_hash = soup.find(lambda tag: "MD5=" in tag.text)
        if not tag_with_hash:
            self.logging_callback(f"[{ISOname}] Could not find HTML tag containing MD5 hash; skipping integrity check.")
            return -1
        md5_raw = parse_hash(tag_with_hash.text, ["MD5=", version_str], -1, logging_callback=self.logging_callback)
        md5_sum = md5_raw.replace("MD5=", "").strip() if md5_raw else None
        if not md5_sum:
            self.logging_callback(f"[{ISOname}] Could not parse MD5 hash; skipping integrity check.")
            return -1
        result = md5_hash_check(local_file, md5_sum, logging_callback=self.logging_callback)
        if not result:
            self.logging_callback(f"[{ISOname}] Hash check failed for file: {local_file}")
        return result

    @cache
    def _get_latest_version(self) -> list[str] | None:
        if(self.soup_download_page is None):
            return None
        version_tag = self.soup_download_page.find("font", {"color": "blue"})
        if not version_tag:
            self.logging_callback(f"[{ISOname}] Could not find the HTML tag containing the version number.")
            return None
        version_text = version_tag.get_text(strip=True)
        return self._str_to_version(
            version_text.split()[2]  # Get 'x.y' from 'Latest version x.y date'
        )

    def _find_in_table(
        self,
        row_name_contains: list[str],
        row_name_doesnt_contain: list[str] | None = None,
    ) -> Tag | None:
        if not row_name_doesnt_contain:
            row_name_doesnt_contain = []
        s: Tag | None = self.soup_download_page.find("table", attrs={"bgcolor": "#B3B3B3"})  # type: ignore
        if not s:
            self.logging_callback(f"[{ISOname}] Could not find the table containing download information.")
            return None
        for tr in s.find_all("tr"):
            text = tr.getText()
            if any(string in text for string in row_name_doesnt_contain):
                continue
            if all(string in text for string in row_name_contains):
                return tr
        self.logging_callback(f"[{ISOname}] Failed to find value in the table.")
        return None

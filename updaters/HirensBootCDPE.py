from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.sha256_hash_check import sha256_hash_check

DOMAIN = "https://www.hirensbootcd.org/"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/download"
FILE_NAME = "HBCD_PE_[[VER]]_x64.iso"
ISOname = "HirensBootCDPE"



class HirensBootCDPE(GenericUpdater):
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
        download_tag: Tag | None = self._find_in_table("Filename")
        if not download_tag:
            self.logging_callback(f"[{ISOname}] Failed to find the Tag containing the download link.")
            return None
        href_attributes = download_tag.find_all(href=True)
        if not href_attributes:
            self.logging_callback(f"[{ISOname}] No download link found in the Tag.")
            return None
        href = href_attributes[0].get("href")
        return str(href) if isinstance(href, str) else None

    def check_integrity(self) -> bool | int | None:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        iso_url = self._get_download_link()
        if not isinstance(local_file, Path) or iso_url is None:
            return -1
        if not verify_file_size(local_file, iso_url, package_name=ISOname, logging_callback=self.logging_callback):
            return False
        sha256_tag = self._find_in_table("SHA-256")
        if not sha256_tag or not sha256_tag.getText():
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not find or extract SHA-256 hash in the download page.")
            return -1
        sha256_val = sha256_tag.getText()
        return sha256_hash_check(local_file, sha256_val, package_name=ISOname, logging_callback=self.logging_callback)

    @cache
    def _get_latest_version(self) -> list[str] | None:
        if self.soup_download_page is None:
            self.logging_callback(f"[{ISOname}] Download page not loaded; cannot extract version information.")
            return None
        s: Tag | None = self.soup_download_page.find(
            "div", attrs={"class": "post-content"}
        )  # type: ignore
        if not s:
            self.logging_callback(f"[{ISOname}] Could not find the div containing version information.")
            return None

        s = s.find("span")  # type: ignore
        if not s:
            self.logging_callback(f"[{ISOname}] Could not find the span containing the version information.")
            return None

        return self._str_to_version(
            s.getText()
            .split("(v")[1]  # Parse from Hiren’s BootCD PE x64 (v1.0.2) – ISO Content
            .split(")")[0]
        )

    def _find_in_table(self, row_name_contains: str) -> Tag | None:
        """
        Find the HTML Tag containing specific information in the download page table.

        Args:
            row_name_contains (str): A string that identifies the row in the table.

        Returns:
            Tag | None: The HTML Tag containing the desired information, or None if not found.

        Raises:
            LookupError: If the table or the specified row_name_contains is not found in the download page.
        """
        s: Tag | None = self.soup_download_page.find("div", attrs={"class": "table-1"})  # type: ignore

        if not s:
            self.logging_callback(f"[{ISOname}] Could not find the table containing download information.")
            return None

        next_is_result = False
        for tr in s.find_all("tr"):
            for td in tr.find_all("td"):
                if next_is_result:
                    return td
                if row_name_contains in td.getText():
                    next_is_result = True

        self.logging_callback(f"[{ISOname}] Failed to find '{row_name_contains}' in the table.")
        return None

"""
NOTE: Windows 10 ISO cannot be reliably hash-checked. Integrity check only compares file size; if the file size is wrong, the file will be deleted and redownloaded. No hashcheck is performed.
"""

from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.generic.WindowsConsumerDownload import WindowsConsumerDownloader
from updaters.shared.robust_get import robust_get
from updaters.shared.fetch_windows_iso_hash import fetch_windows_iso_hash
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.parse_version_from_soup import parse_version_from_soup
from updaters.shared.sha256_hash_check import sha256_hash_check


DOMAIN = "https://www.microsoft.com"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/en-us/software-download/windows10ISO"
FILE_NAME = "Win10_[[VER]]_[[LANG]]_x64v1.iso"
ISOname = "Windows10"



class Windows10(GenericUpdater):
 
    def check_integrity(self) -> bool | int | None:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(local_file, Path):
            return -1
        download_link = self._get_download_link()
        if download_link is None:
            return -1
        # First, verify file size
        size_ok = verify_file_size(local_file, download_link, package_name=ISOname, logging_callback=self.logging_callback)
        if not size_ok:
            return size_ok
        # Then, verify SHA256 hash
        search_label = f"{self.lang} 64-bit"
        url = "https://www.microsoft.com/en-ca/software-download/windows10ISO"
        expected_hash = fetch_windows_iso_hash(search_label, url, self.headers, logging_callback=self.logging_callback)
        if not expected_hash:
            if self.logging_callback:
                self.logging_callback(f"[Windows10] Could not fetch expected SHA256 hash for {search_label}")
            return None
        hash_ok = sha256_hash_check(local_file, expected_hash, logging_callback=self.logging_callback)
        if not hash_ok:
            if self.logging_callback:
                self.logging_callback(f"[Windows10] SHA256 hash check failed for {local_file}")
            return False
        return True

    """
    A class representing an updater for Windows 10.

    Attributes:
        download_page (requests.Response): The HTTP response containing the download page HTML.
        soup_download_page (BeautifulSoup): The parsed HTML content of the download page.

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """


    def __init__(self, folder_path: Path, lang: str, *args, **kwargs):
        self.valid_langs = [
            "Arabic",
            "Brazilian Portuguese",
            "Bulgarian",
            "Chinese",
            "Chinese",
            "Croatian",
            "Czech",
            "Danish",
            "Dutch",
            "English",
            "English International",
            "Estonian",
            "Finnish",
            "French",
            "French Canadian",
            "German",
            "Greek",
            "Hebrew",
            "Hungarian",
            "Italian",
            "Japanese",
            "Korean",
            "Latvian",
            "Lithuanian",
            "Norwegian",
            "Polish",
            "Portuguese",
            "Romanian",
            "Russian",
            "Serbian Latin",
            "Slovak",
            "Slovenian",
            "Spanish",
            "Spanish (Mexico)",
            "Swedish",
            "Thai",
            "Turkish",
            "Ukrainian",
        ]
        # Make the parameter case insensitive, and find back the correct case using valid_langs
        self.lang = next(
            valid_lang
            for valid_lang in self.valid_langs
            if valid_lang.lower() == lang.lower()
        )
        file_path = folder_path / FILE_NAME.replace("[[LANG]]", self.lang.replace(" ", "_").replace("(", "").replace(")", ""))
        super().__init__(file_path, *args, **kwargs)

        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "referer": "folfy.blue",
        }

        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, headers=self.headers, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.soup_download_page = None
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(self.download_page.content.decode("utf-8"), features="html.parser")

    @cache
    def _get_download_link(self) -> str | None:
        return WindowsConsumerDownloader.windows_consumer_download("10", self.lang, logging_callback=self.logging_callback)

    @cache
    def _get_latest_version(self) -> list[str] | None:
        tag_path = [
            ("div", {"id": "SoftwareDownload_EditionSelection"}),
            ("h2", {})
        ]
        try:
            version = parse_version_from_soup(self.soup_download_page, tag_path, splitter="H")
            if version is None or not version:
                return None
            return version
        except Exception as e:
            if self.logging_callback:
                self.logging_callback(f"[Windows10] Exception while parsing version: {e}")
            return None

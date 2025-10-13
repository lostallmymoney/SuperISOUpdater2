from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.check_remote_integrity import check_remote_integrity
from updaters.shared.robust_get import robust_get
import re

ISOname = "UltimateBootCD"
OLDERGEEKS_PAGE_URL = "https://www.oldergeeks.com/downloads/file.php?id=242"
OLDERGEEKS_DL_URL = "https://www.oldergeeks.com/downloads/download.php?id=242"
FILE_NAME_TEMPLATE = "ubcd[[VER]].iso"

class UltimateBootCD(GenericUpdater):
    def __init__(self, folder_path: Path, *args, **kwargs):
        FILE_NAME = "ubcd[[VER]].iso"
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        self.folder_path = folder_path

    @cache
    def _get_latest_version(self) -> list[str] | None:
        resp = robust_get(OLDERGEEKS_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if not resp or getattr(resp, 'status_code', None) != 200:
            if self.logging_callback:
                self.logging_callback(f"[UltimateBootCD] Could not load download page: {OLDERGEEKS_PAGE_URL}")
            return None
        soup = BeautifulSoup(resp.content.decode(resp.encoding or "utf-8", errors="replace"), features="html.parser")
        h1 = soup.find("h1")
        version = None
        if h1 and "Ultimate Boot CD v" in h1.text:
            m = re.search(r"v([\d.]+)", h1.text)
            if m:
                version = m.group(1)
        if not version:
            if self.logging_callback:
                self.logging_callback(f"[UltimateBootCD] Could not parse version from heading.")
            return None
        return version.split('.')

    @cache
    def _get_download_link(self) -> str | None:
        return OLDERGEEKS_DL_URL

    def _get_complete_normalized_file_path(self, absolute=True, latest=False):
        version = self._get_latest_version()
        if not version:
            filename = "ubcd.iso"
        else:
            filename = f"ubcd{''.join(version)}.iso"
        path = self.folder_path / filename
        return path.resolve() if absolute else path

    def check_integrity(self) -> int | bool:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = OLDERGEEKS_DL_URL
        if not isinstance(local_file, Path):
            if self.logging_callback:
                self.logging_callback(f"[UltimateBootCD] Could not resolve local file path for integrity check.")
            return -1
        if download_link is None:
            if self.logging_callback:
                self.logging_callback(f"[UltimateBootCD] No valid download link for integrity check.")
            return -1
        if verify_file_size(local_file, download_link, package_name=ISOname, logging_callback=self.logging_callback) is False:
            if self.logging_callback:
                self.logging_callback(f"[UltimateBootCD] File size check failed.")
            return False
        # Fetch the OlderGeeks page and parse the md5sum
        resp = robust_get(OLDERGEEKS_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        md5sum = None
        if resp and getattr(resp, 'status_code', None) == 200:
            import re
            m = re.search(r"md5sum:\s*([a-fA-F0-9]{32})", resp.text)
            if m:
                md5sum = m.group(1)
        if not md5sum:
            if self.logging_callback:
                self.logging_callback(f"[UltimateBootCD] Could not find md5sum on the page.")
            return False
        # Use shared md5_hash_check with the found md5sum
        from updaters.shared.md5_hash_check import md5_hash_check
        result = md5_hash_check(local_file, md5sum, logging_callback=self.logging_callback)
        if not result and self.logging_callback:
            self.logging_callback(f"[UltimateBootCD] MD5 check failed. Expected {md5sum}.")
        return result

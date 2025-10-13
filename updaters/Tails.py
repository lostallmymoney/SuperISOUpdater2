from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.sha256_hash_check import sha256_hash_check
import json

DOMAIN = "https://mirrors.edge.kernel.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/tails/stable"
FILE_NAME = "tails-amd64-[[VER]].img"
PUB_KEY_URL = "https://tails.net/tails-signing.key"
ISOname = "Tails"
JSON_URL = "https://tails.net/install/v2/Tails/amd64/stable/latest.json"

class Tails(GenericUpdater):
    """
    A class representing an updater for Tails.
    """
    def __init__(self, folder_path: Path, *args, **kwargs):
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.soup_download_page = None
            return
        self.download_page = resp
        self.soup_download_page = BeautifulSoup(self.download_page.content.decode('utf-8'), features="html.parser")

    @cache
    def _get_download_link(self) -> str | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            return None
        latest_version_str = self._version_to_str(latest_version)
        return f"{DOWNLOAD_PAGE_URL}/tails-amd64-{latest_version_str}/{self._get_complete_normalized_file_path(absolute=False)}"

    def check_integrity(self) -> bool | int | None:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if download_link is None or not isinstance(local_file, Path):
            return -1
        if verify_file_size(local_file, download_link, package_name=ISOname, logging_callback=self.logging_callback) is False:
            return False

        resp_json = robust_get(JSON_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp_json is None or resp_json.status_code != 200:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not fetch Tails JSON metadata for SHA256 check.")
            return False
        try:
            data = json.loads(resp_json.text)
            img_sha256 = None
            for inst in data.get("installations", []):
                for path in inst.get("installation-paths", []):
                    if path.get("type") == "img":
                        for tf in path.get("target-files", []):
                            img_sha256 = tf.get("sha256")
                            break
                if img_sha256:
                    break
            if not img_sha256:
                if self.logging_callback:
                    self.logging_callback(f"[{ISOname}] No SHA256 found for .img in Tails JSON metadata.")
                return False
        except Exception as e:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Error parsing Tails JSON metadata: {e}")
            return False

        return sha256_hash_check(local_file, img_sha256, package_name=ISOname, logging_callback=self.logging_callback)

    @cache
    def _get_latest_version(self) -> list[str] | None:
        download_a_tags = self.soup_download_page.find_all("a", href=True) if self.soup_download_page else []
        if not download_a_tags:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No valid {ISOname} version found on the download page.")
            return None

        local_version = self._get_local_version()
        latest = local_version or []

        for a_tag in download_a_tags:
            href = a_tag.get("href")
            if not isinstance(href, str):
                continue
            if "tails-amd64" not in href:
                continue
            version = href.split("-")[-1]
            if not version or not version[0].isnumeric():
                continue
            version_number = self._str_to_version(version[:-1])
            if self._compare_version_numbers(latest, version_number):
                latest = version_number

        if not latest:
            return None
        return latest

import re
from functools import cache
from pathlib import Path
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.parse_hash import parse_hash
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.shared.sha512_hash_check import sha512_hash_check
from updaters.shared.md5_hash_check import md5_hash_check

DOMAIN = "https://gitlab.manjaro.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/web/iso-info/-/raw/master/file-info.json"
FILE_NAME = "manjaro-[[EDITION]]-[[VER]]-linux.iso"

ISOname = "Manjaro"


class Manjaro(GenericUpdater):
    """
    A class representing an updater for Manjaro.

    Attributes:
        valid_editions (list[str]): List of valid editions to use
        edition (str): Edition to download
        file_info_json (dict[Any, Any]): JSON file containing file information for each edition

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["plasma", "xfce", "gnome", "cinnamon", "i3"]
        self.edition = edition.lower()
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None:
            self.file_info_json = None
            return
        self.file_info_json = resp.json()
        self.file_info_json["releases"] = self.file_info_json["official"] | self.file_info_json["community"]

    @cache
    def _get_download_link(self) -> str | None:
        if not self.file_info_json:
            return None
        return self.file_info_json["releases"][self.edition]["image"]

    def check_integrity(self) -> bool | int | None:
        if not self.file_info_json:
            self.logging_callback(f"No file info JSON loaded.")
            return False
        checksum_url = self.file_info_json["releases"][self.edition]["checksum"]
        if checksum_url.endswith(".sha512"):
            hash_type = "sha512"
        elif checksum_url.endswith(".sha256"):
            hash_type = "sha256"
        elif checksum_url.endswith(".md5"):
            hash_type = "md5"
        else:
            hash_type = "sha256"  # fallback
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(local_file, Path):
            return -1
        local_file = Path(local_file)
        download_link = self._get_download_link()
        if download_link is None:
            return -1
        if not verify_file_size(local_file, download_link, logging_callback=self.logging_callback):
            return False
        # Hash check
        resp = robust_get(checksum_url, retries=3, delay=1, logging_callback=self.logging_callback)
        if resp is None:
            self.logging_callback(f"Could not fetch checksum file: robust_get failed")
            return -1
        hash_file = resp.text
        hash_val = parse_hash(hash_file, [], 0, logging_callback=self.logging_callback)
        if not hash_val:
            return -1
        if hash_type == "sha512":
            return sha512_hash_check(local_file, hash_val, logging_callback=self.logging_callback)
        elif hash_type == "sha256":
            return sha256_hash_check(local_file, hash_val, logging_callback=self.logging_callback)
        elif hash_type == "md5":
            return md5_hash_check(local_file, hash_val, logging_callback=self.logging_callback)
        return -1

    @cache
    def _get_latest_version(self) -> list[str] | None:
        download_link = self._get_download_link()
        if not download_link:
            self.logging_callback(f"Could not get download link")
            return None
        latest_version_regex = re.search(r"manjaro-\w+-(.+?)-", download_link)
        if latest_version_regex:
            return self._str_to_version(latest_version_regex.group(1))
        self.logging_callback(f"Could not find the latest available version")
        return None



from functools import cache
from pathlib import Path
from urllib.parse import urlparse, urlunparse
import re
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.github_get_latest_version import github_get_latest_version
from updaters.shared.parse_github_release import parse_github_release
from updaters.shared.parse_hash import parse_hash
from updaters.shared.sha1_hash_check import sha1_hash_check
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size

FILE_NAME = "shredos-[[VER]].img"
ISOname = "ShredOS"


class ShredOS(GenericUpdater):
    """
    A class representing an updater for ShredOS.

    Attributes:
        valid_editions (list[str]): List of valid editions to use
        edition (str): Edition to download

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, *args, **kwargs):
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)

        release = github_get_latest_version("PartialVolume", "shredos.x86_64", self.logging_callback)
        info = parse_github_release(release, self.logging_callback) if release is not None else None
        self.release_info = info if info is not None else {}

    @cache
    def _get_download_link(self) -> str | None:
        files = self.release_info.get("files") if self.release_info else None
        if not files:
            return None
        for filename, download_link in files.items():
            if filename.endswith(".img") and "x86-64" in filename:
                return download_link
        return None

    def check_integrity(self) -> bool | int | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            self.logging_callback("Could not determine latest version for integrity check.")
            return -1

        download_link = self._get_download_link()
        if download_link is None:
            self.logging_callback("Could not resolve download link for integrity check.")
            return -1

        sha1_url = self._get_sha1_url(download_link)
        if not sha1_url:
            self.logging_callback("Could not resolve SHA1 URL for integrity check.")
            return -1

        resp = robust_get(sha1_url, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or getattr(resp, "status_code", 0) != 200:
            self.logging_callback(f"Could not fetch SHA1 sums from {sha1_url}")
            return -1

        sha1_sums = resp.text.strip()
        download_filename = self._get_download_filename(download_link)
        sha1_sum = parse_hash(
            sha1_sums,
            [download_filename] if download_filename else [],
            0,
            logging_callback=self.logging_callback
        )
        if not sha1_sum:
            # Fallback: extract the first SHA1-looking token in the file
            match = re.search(r"\b[a-fA-F0-9]{40}\b", sha1_sums)
            sha1_sum = match.group(0) if match else None
        if not sha1_sum:
            self.logging_callback("Could not parse SHA1 sum for integrity check.")
            return -1

        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(local_file, Path) or not local_file.exists():
            self.logging_callback("Local file does not exist for integrity check.")
            return None
        if verify_file_size(local_file, download_link, logging_callback=self.logging_callback) is False:
            return False
        if sha1_hash_check(local_file, sha1_sum, logging_callback=self.logging_callback) is False:
            return False
        return True

    def _get_download_filename(self, download_link: str) -> str | None:
        parsed = urlparse(download_link)
        filename = Path(parsed.path).name
        if filename == "download":
            filename = Path(parsed.path).parent.name
        return filename or None

    def _get_sha1_url(self, download_link: str) -> str | None:
        parsed = urlparse(download_link)
        path = parsed.path
        filename = Path(path).name
        if filename == "download":
            path = str(Path(path).parent)
            filename = Path(path).name
        if not filename:
            return None
        if not filename.endswith(".sha1"):
            path = f"{path}.sha1"
        return urlunparse(parsed._replace(path=path))

    @cache
    def _get_latest_version(self) -> list[str] | None:
        tag = self.release_info.get("tag") if self.release_info else None
        if not tag or "v" not in tag or "_" not in tag:
            return None
        start_index = tag.find("v")
        end_index = tag.find("_")
        version = tag[start_index + 1 : end_index]
        return self._str_to_version(version)



from functools import cache
from pathlib import Path
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.github_get_latest_version import github_get_latest_version
from updaters.shared.parse_github_release import parse_github_release
from updaters.shared.parse_hash import parse_hash
from updaters.shared.sha1_hash_check import sha1_hash_check
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
        sha1_sums = self.release_info.get("text") if self.release_info else None
        if not sha1_sums:
            self.logging_callback("No SHA1 sums available for integrity check.")
            return -1

        latest_version = self._get_latest_version()
        if latest_version is None:
            self.logging_callback("Could not determine latest version for integrity check.")
            return -1

        sha1_sum = parse_hash(
            sha1_sums,
            [
                "sha1",
                self._version_to_str(latest_version),
                "x86-64",
                ".img",
            ],
            1,
            logging_callback=self.logging_callback
        )
        if not sha1_sum:
            self.logging_callback("Could not parse SHA1 sum for integrity check.")
            return -1

        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if download_link is None:
            self.logging_callback("Could not resolve download link for integrity check.")
            return -1
        if not isinstance(local_file, Path) or not local_file.exists():
            self.logging_callback("Local file does not exist for integrity check.")
            return None
        if verify_file_size(local_file, download_link, logging_callback=self.logging_callback) is False:
            return False
        if sha1_hash_check(local_file, sha1_sum, logging_callback=self.logging_callback) is False:
            return False
        return True

    @cache
    def _get_latest_version(self) -> list[str] | None:
        tag = self.release_info.get("tag") if self.release_info else None
        if not tag or "v" not in tag or "_" not in tag:
            return None
        start_index = tag.find("v")
        end_index = tag.find("_")
        version = tag[start_index + 1 : end_index]
        return self._str_to_version(version)


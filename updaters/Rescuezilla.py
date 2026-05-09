from functools import cache
from pathlib import Path
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.github_get_latest_version import github_get_latest_version
from updaters.shared.parse_github_release import parse_github_release
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.check_remote_integrity import check_remote_integrity

FILE_NAME = "rescuezilla-[[VER]]-64bit.[[EDITION]].iso"
ISOname = "Rescuezilla"


class Rescuezilla(GenericUpdater):
    
    """
    A class representing an updater for Rescuezilla.

    Attributes:
        valid_editions (list[str]): List of valid editions to use
        edition (str): Edition to download
        release_info (dict): Github release information

    Note:
        This class inherits from the abstract base class GenericUpdater.
    """

    def __init__(self, folder_path: Path, edition: str, *args, **kwargs) -> None:
        self.valid_editions = ["bionic", "focal", "jammy", "noble"]
        self.edition = edition.lower()
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)

        release = github_get_latest_version("rescuezilla", "rescuezilla", self.logging_callback)
        info = parse_github_release(release, self.logging_callback) if release is not None else None
        self.release_info = info if info is not None else {}

    @cache
    def _get_download_link(self) -> str | None:
        files = self.release_info.get("files") if self.release_info else None
        if not files:
            return None
        key = str(self._get_complete_normalized_file_path(absolute=False))
        return files.get(key)


    def check_integrity(self) -> bool | int | None:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if not isinstance(local_file, Path) or download_link is None:
            self.logging_callback("Could not resolve file path or download link for integrity check.")
            return None
        if verify_file_size(local_file, download_link, logging_callback=self.logging_callback) is False:
            return False
        files = self.release_info.get("files") if self.release_info else None
        sha256_url = files.get("SHA256SUM") if files else None
        if sha256_url:
            return check_remote_integrity(
                hash_url=sha256_url,
                local_file=local_file,
                hash_type="sha256",
                parse_hash_args=([str(self._get_complete_normalized_file_path(absolute=False))], 0),
                logging_callback=self.logging_callback,
            )
        return False

    @cache
    def _get_latest_version(self) -> list[str] | None:
        tag = self.release_info.get("tag") if self.release_info else None
        if not tag:
            return None
        return self._str_to_version(tag)

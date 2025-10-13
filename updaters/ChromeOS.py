from functools import cache
from pathlib import Path
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_download import robust_download
from updaters.shared.list_zip_files import list_zip_files
from updaters.shared.extract_file_from_zip import extract_file_from_zip
from updaters.shared.sha1_hash_check import sha1_hash_check
import os

DOMAIN = "https://dl.google.com"
FILE_NAME = "chromeos_[[VER]]_[[EDITION]].img"
ISOname = "ChromeOS"


class ChromeOS(GenericUpdater):
    @cache
    def _get_download_link(self) -> str | None:
        if not self.cur_edition_info:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No edition info available for download link.")
            return None
        return self.cur_edition_info.get("url")
    
    def __init__(self, folder_path: Path, edition: str = "stable", *args, **kwargs) -> None:
        self.valid_editions = ["ltc", "ltr", "stable"]
        self.edition = edition.lower() if edition else "stable"
        file_path = Path(folder_path) / FILE_NAME if 'FILE_NAME' in globals() else folder_path
        super().__init__(file_path, *args, **kwargs)
        import requests
        self.chromium_releases_info: list[dict] = requests.get(
            f"{DOMAIN}/dl/edgedl/chromeos/recovery/cloudready_recovery2.json"
        ).json()
        self.cur_edition_info: dict | None = next(
            d
            for d in self.chromium_releases_info
            if d["channel"].lower() == self.edition
        )
        if not self.cur_edition_info:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No release info found for edition '{self.edition}'")
            self.cur_edition_info = None
            return

    def check_integrity(self) -> bool | int | None:
        if not self.cur_edition_info:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No edition info available for integrity check.")
            return -1
        sha1_sum = self.cur_edition_info.get("sha1")
        if not sha1_sum:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No SHA1 hash found for integrity check.")
            return -1
        archive_path = self._get_archive_path()
        if(archive_path is None):
            return -1
        return sha1_hash_check(archive_path, sha1_sum, logging_callback=self.logging_callback)

    def _get_archive_path(self) -> Path | None:
        # Always use .zip for the downloaded archive
        img_path = self._get_complete_normalized_file_path(
            absolute=True,
            latest=True
        )
        if not isinstance(img_path, Path):
            return None
        return img_path.with_suffix('.zip')

    def install_latest_version(self, retries: int = 3) -> bool | None:
        archive_path = self._get_archive_path()
        if not self.cur_edition_info or not isinstance(archive_path, Path):
            return None
        img_path = archive_path.with_suffix("").with_suffix(".img")
        download_link = self._get_download_link()
        if not isinstance(download_link, str):
            return None
        
        result = robust_download(download_link, local_file=archive_path, retries=retries, logging_callback=self.logging_callback)
        if not result:
            return None
        sha1_sum = self.cur_edition_info.get("sha1")
        if not sha1_sum:
            archive_path.unlink(missing_ok=True)
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No SHA1 hash found for integrity check.")
            return None
        if not sha1_hash_check(archive_path, sha1_sum, logging_callback=self.logging_callback):
            archive_path.unlink(missing_ok=True)
            return False
        # Find the .bin file in the archive
        file_list = list_zip_files(archive_path)
        bin_candidates = [f for f in file_list if f.lower().endswith('.bin')]
        if not bin_candidates:
            archive_path.unlink(missing_ok=True)
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No .bin file found in archive.")
            return None
        to_extract = bin_candidates[0]
        # Extract the .bin file
        extract_file_from_zip(archive_path, to_extract, img_path.parent)
        extracted_file = img_path.parent / to_extract
        os.replace(extracted_file, img_path)
        #archive_path.unlink(missing_ok=True) Leave the archive for future integrity checks
        return True

    @cache
    def _get_latest_version(self) -> list[str] | None:
        if not self.cur_edition_info:
            return None
        return self._str_to_version(self.cur_edition_info.get("version", "0.0.0"))

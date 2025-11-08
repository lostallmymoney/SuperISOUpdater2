
from functools import cache
from pathlib import Path
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get
from updaters.shared.fetch_expected_file_size import fetch_expected_file_size as fetch_expected_file_size
from updaters.shared.verify_file_size import verify_file_size

from updaters.shared.check_remote_integrity import check_remote_integrity


DOMAIN = "https://download.opensuse.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/download/distribution/[[EDITION]]"
FILE_NAME = "openSUSE-[[EDITION]]-[[VER]]-DVD-x86_64-Current.iso"

ISOname = "OpenSUSE"


class OpenSUSE(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = ["leap", "leap-micro", "jump"]
        self.edition = edition.lower()
        self.download_page_url = DOWNLOAD_PAGE_URL.replace("[[EDITION]]", self.edition)
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)

    def _capitalize_edition(self) -> str:
        return "-".join([s.capitalize() for s in self.edition.split("-")])

    @cache
    def _get_download_link(self) -> str | None:
        latest_version = self._get_latest_version()
        if latest_version is None:
            return None
        latest_version_str = self._version_to_str(latest_version)
        url = f"{self.download_page_url}/{latest_version_str}"
        resp = robust_get(f"{url}?jsontable", retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None:
            return ""
        edition_page = resp.json()["data"]
        if any("product" in item["name"] for item in edition_page):
            url += "/product"
        if self.edition != "leap-micro":
            latest_version_str += "-NET"
        return f"{url}/iso/openSUSE-{self._capitalize_edition()}-{latest_version_str}-x86_64{"-Current" if self.edition != "leap-micro" else ""}.iso"

    def check_integrity(self) -> bool | int | None:
        file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(file, Path):
            self.logging_callback("File path is not a valid Path object for integrity check.")
            return -1
        link = self._get_download_link()
        if not link:
            self.logging_callback("Could not determine download link for integrity check.")
            return -1
        if not verify_file_size(file, link, logging_callback=self.logging_callback):
            return False
        # Use check_remote_integrity for hash check
        return check_remote_integrity(
            f"{link}.sha256",
            file,
            "sha256",
            ([], 0),
            logging_callback=self.logging_callback
        )

    @cache
    def _get_latest_version(self) -> list[str] | None:
        resp = robust_get(f"{self.download_page_url}?jsontable", retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None:
            self.logging_callback(f"[{ISOname}] Failed to fetch jsontable from '{self.download_page_url}'")
            return None
        data = resp.json()["data"]
        local_version = self._get_local_version()
        latest = local_version or []
        for i in range(len(data)):
            if "42" in data[i]["name"]:
                continue
            version_number = self._str_to_version(data[i]["name"][:-1])
            if self._compare_version_numbers(latest, version_number):
                sub_url = f"{self.download_page_url}/{self._version_to_str(version_number)}?jsontable"
                sub_resp = robust_get(sub_url, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
                if sub_resp is None:
                    continue
                sub_data = sub_resp.json()["data"]
                if not any("iso" in item["name"] or "product" in item["name"] for item in sub_data):
                    continue
                latest = version_number
        return latest

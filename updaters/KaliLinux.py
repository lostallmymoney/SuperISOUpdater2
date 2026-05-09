from functools import cache
from pathlib import Path
from urllib.parse import urljoin
import re
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.robust_get import robust_get

from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.torrent_download import download_torrent
from updaters.shared.robust_download import robust_download
from updaters.shared.check_remote_integrity import check_remote_integrity

DOMAIN = "https://cdimage.kali.org"
DOWNLOAD_PAGE_URL = urljoin(DOMAIN, "current/")
FILE_NAME = "kali-linux-[[VER]]-[[EDITION]].iso"
ISOname = "KaliLinux"



class KaliLinux(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = [
            "installer-amd64",
            "installer-everything-amd64",
            "installer-arm64",
            "installer-netinst-amd64",
            "live-everything-amd64",
            "live-amd64",
            "live-arm64",
        ]
        self.edition = edition.lower()
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.download_page = None
            self.html_content = None
            return
        self.download_page = resp
        self.html_content = self.download_page.text

    @cache
    def _get_download_link(self) -> str | None:
        """
        Extract the best matching href for the edition/version from the HTML.
        Prefer the shortest href (i.e., .iso before .iso.torrent) for a given edition/version.
        """
        if not self.html_content:
            return None
        hrefs = re.findall(r'<a[^>]+href=["\']([^"\'>]+)["\']', self.html_content)
        if not hrefs:
            return None
        version = self._get_latest_version()
        if not version:
            return None
        version_str = self._version_to_str(version)
        base_name = f"kali-linux-{version_str}-{self.edition}.iso"
        # Collect all matching hrefs (iso and iso.torrent)
        matches = [href for href in hrefs if href.endswith(base_name) or href.endswith(base_name + ".torrent")]
        if not matches:
            return None
        # Prefer the shortest href (i.e., .iso before .iso.torrent)
        best = min(matches, key=len)
        return urljoin(DOWNLOAD_PAGE_URL, best)


    def check_integrity(self, *args, **kwargs) -> bool | int | None:
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(local_file, Path):
            self.logging_callback(f"Invalid local file path: {local_file}")
            return -1

        iso_url = self._get_download_link()
        if not iso_url or iso_url is None:
            self.logging_callback("No valid download link found for this edition/version.")
            return -1

        if iso_url.endswith('.torrent'):
            # Download the .torrent file if missing
            torrent_filename = iso_url.split('/')[-1]
            torrent_path = local_file.parent / torrent_filename
            if not torrent_path.exists():
                from updaters.shared.robust_download import robust_download
                self.logging_callback(f"[check_integrity] Downloading torrent file: {iso_url}")
                success = robust_download(iso_url, str(torrent_path), logging_callback=self.logging_callback)
                if not success or not torrent_path.exists():
                    self.logging_callback(f"Torrent file missing: {torrent_path}")
                    return False
        else:
            local_file = self._get_complete_normalized_file_path(absolute=True)
            if not isinstance(local_file, Path):
                self.logging_callback(f"Invalid local file path: {local_file}")
                return -1
            # First, verify file size
            if not verify_file_size(local_file, iso_url, logging_callback=self.logging_callback):
                return False
        

        sha256_url = urljoin(DOWNLOAD_PAGE_URL, "SHA256SUMS")
        match_strings = [str(self._get_complete_normalized_file_path(absolute=False))]
        return check_remote_integrity(
                sha256_url,
                local_file,
                "sha256",
                (match_strings, 0),
                logging_callback=self.logging_callback
            )

    def install_latest_version(self, *args, **kwargs) -> None | bool:
        download_url = self._get_download_link()
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if download_url and download_url.endswith('.torrent'):
            torrent_filename = download_url.split('/')[-1]
            torrent_path = local_file.parent / torrent_filename
            if not torrent_path.exists():
                self.logging_callback(f"[install_latest_version] Downloading torrent file: {download_url}")
                robust_download(download_url, str(torrent_path), logging_callback=self.logging_callback)
            self.logging_callback(f"[install_latest_version] Using torrent_download to fetch ISO from {torrent_path}")
            return download_torrent(str(torrent_path), str(local_file.parent), logging_callback=self.logging_callback)
        # Otherwise, use the base class method for direct ISO download
        return super().install_latest_version(*args, **kwargs)


    @cache
    def _get_latest_version(self) -> list[str] | None:
        if not self.html_content:
            self.logging_callback(f"No HTML content to parse for version.")
            return None
        # Use regex to find all hrefs in <a> tags
        hrefs = re.findall(r'<a[^>]+href=["\']([^"\'>]+)["\']', self.html_content)
        if not hrefs:
            self.logging_callback(f"Could not parse the download page for version.")
            return None
        # Try to find the first href that matches the expected ISO pattern for this edition
        # Accepts both installer/live and everything/non-everything variants
        edition_pattern = re.escape(self.edition)
        pattern = re.compile(r'kali-linux-([0-9A-Za-z_.-]+)-' + edition_pattern + r'\.iso')
        for href in hrefs:
            m = pattern.search(href)
            if m:
                version_str = m.group(1)
                return self._str_to_version(version_str)
        self.logging_callback(f"Could not determine the latest version string for edition '{self.edition}'.")
        return None

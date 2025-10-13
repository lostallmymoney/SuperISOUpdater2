
from functools import cache
from pathlib import Path
from updaters.shared.fetch_hashes_from_url import fetch_hashes_from_url
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.generic.GenericUpdater import GenericUpdater

DOMAIN = "https://gparted.org"
FILE_NAME = "gparted-live-[[VER]]-amd64.iso"
ISOname = "GPartedLive"

class GPartedLive(GenericUpdater):
    """
    Updater for GParted Live ISO. Fetches SHA256 hash from the correct section of the checksum file.
    """
    def __init__(self, folder_path: Path, *args, **kwargs):
        file_path = folder_path / FILE_NAME
        super().__init__(file_path, *args, **kwargs)

    def _fetch_sha256_hash(self) -> str:
        try:
            content = fetch_hashes_from_url("https://gparted.org/gparted-live/stable/CHECKSUMS.TXT")
        except Exception as e:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not fetch CHECKSUMS.TXT: {e}")
            return ""
        lines = content.splitlines()
        in_sha256 = False
        for line in lines:
            if line.strip().startswith("### SHA256SUMS"):
                in_sha256 = True
                continue
            if in_sha256:
                if line.strip().startswith("###") and not line.strip().startswith("### SHA256SUMS"):
                    break
                if line.strip().endswith(".iso"):
                    parts = line.strip().split()
                    if parts:
                        return parts[0]
        return ""

    @cache
    def _get_download_link(self) -> str | None:
        """
        Build the download link for the latest GParted Live ISO.
        """
        latest_version = self._get_latest_version()
        if latest_version is None:
            return None
        ver = self._version_to_str(latest_version)
        if not ver:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not determine version for download link.")
            return None
        return f"https://downloads.sourceforge.net/gparted/gparted-live-{self._get_gparted_version_style(ver)}-amd64.iso"

    def check_integrity(self, *args, **kwargs) -> bool | int | None:
        """
        Check the integrity of the local ISO using the SHA256 hash from the checksum file.
        """
        local_file = self._get_complete_normalized_file_path(absolute=True)
        download_link = self._get_download_link()
        if not download_link:
            return -1
        if not isinstance(local_file, Path):
            return -1
        if not verify_file_size(local_file, download_link, package_name=ISOname, logging_callback=self.logging_callback):
            return False
        sha256_val = self._fetch_sha256_hash()
        if not sha256_val:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not fetch SHA256 hash for file.")
            return -1
        result = sha256_hash_check(local_file, sha256_val, package_name=ISOname, logging_callback=self.logging_callback)
        return bool(result)

    @cache
    def _get_latest_version(self) -> list[str] | None:
        """
        Extract the latest version from the SHA256SUMS section of the checksum file.
        """
        try:
            content = fetch_hashes_from_url("https://gparted.org/gparted-live/stable/CHECKSUMS.TXT")
        except Exception as e:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No checksum file available to determine version: {e}")
            return None
        lines = [line for line in content.splitlines() if line.strip() and line.strip().endswith(".iso")]
        if not lines:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Checksum file is empty or no .iso lines found.")
            return None
        # Use the last .iso line for the latest version
        version_line = lines[-1]
        split_line = version_line.split()
        if not split_line:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Last non-empty line in checksum file is empty or malformed: '{version_line}'")
            return None
        version = split_line[-1]
        version_parts = version.split("-")
        if len(version_parts) < 4:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Version string does not have enough parts: '{version}'")
            return None
        version_str = ".".join(version_parts[2:4])
        return self._str_to_version(version_str)


    @cache
    def _get_gparted_version_style(self, version: str) -> str:
        """
        Convert the version string from "x.y.z.a" to "x.y.z-a" format, as used by GParted Live.
        """
        return "-".join(version.rsplit(".", 1))

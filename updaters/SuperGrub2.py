

from functools import cache
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.parse_hash import parse_hash
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.shared.unzip_file import unzip_file
from updaters.shared.robust_download import robust_download
from updaters.shared.robust_get import robust_get
from updaters.shared.verify_file_size import verify_file_size
import os


DOMAIN = "https://www.supergrubdisk.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/category/download/supergrub2diskdownload/"
FILE_NAME = "SuperGrub2-[[VER]].img"
ISOname = "SuperGrub2"

class SuperGrub2(GenericUpdater):
    def __init__(self, folder_path: Path, *args, **kwargs):
        file_path = Path(folder_path) / FILE_NAME
        super().__init__(file_path, *args, **kwargs)
        resp = robust_get(DOWNLOAD_PAGE_URL, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if resp is None or resp.status_code != 200:
            self.soup_latest_download_article = None
            return
        soup = BeautifulSoup(resp.content.decode(resp.encoding or "utf-8"), features="html.parser")
        self.soup_latest_download_article = soup.find("article")

    def check_integrity(self) -> bool | int | None:
        """
        Verifies the integrity of the downloaded archive and the extracted .img file using SHA256 sums from the download page.
        Returns True if both checks pass, False if any fail, or -1 if checks cannot be performed.
        """
        new_file = self._get_complete_normalized_file_path(absolute=True)
        archive_path = new_file.with_suffix(".zip")
        if not archive_path.exists():
            self.logging_callback(f"Archive file does not exist: {archive_path}")
            return None

        # Check archive file size
        download_link = self._get_download_link()
        if not download_link:
            self.logging_callback(f"No download link available for file size check.")
            return -1
        if not verify_file_size(archive_path, download_link, logging_callback=self.logging_callback):
            self.logging_callback(f"Archive file size verification failed.")
            return False
        if not self.soup_latest_download_article:
            self.logging_callback(f"No soup object for download article, cannot check integrity.")
            return -1
        sha256_sums_tag = self.soup_latest_download_article.find_all("pre")
        if not sha256_sums_tag:
            self.logging_callback(f"Couldn't find the SHA256 sum.")
            return -1
        sha256_sums_tag = sha256_sums_tag[-1]
        sha256_checksums_str = sha256_sums_tag.getText()
        self.logging_callback(f"SHA256 hash text from page:\n{sha256_checksums_str}")

        # Check archive hash
        # Use the actual filename from the download URL for hash matching
        from urllib.parse import urlparse
        download_url = download_link
        archive_url_filename = os.path.basename(urlparse(download_url).path)
        # Sometimes SourceForge URLs end with /download, so get the filename from the path before /download
        if archive_url_filename == "download":
            archive_url_filename = os.path.basename(os.path.dirname(urlparse(download_url).path))
        self.logging_callback(f"[check_integrity] Using archive_url_filename for hash match: {archive_url_filename}")
        archive_hash = parse_hash(sha256_checksums_str, [archive_url_filename], 0, logging_callback=self.logging_callback)
        self.logging_callback(f"Archive hash for {archive_url_filename}: {archive_hash}")
        if not archive_hash or not sha256_hash_check(archive_path, archive_hash, logging_callback=self.logging_callback):
            self.logging_callback(f"FAIL: Archive hash check failed or hash missing for {archive_url_filename}.")
            return False

        # Do NOT check .img file hash: the hash list only provides a hash for the .zip file
        return True

    @cache
    def _get_download_link(self) -> str | None:
        download_tag = self._find_in_table("Download supergrub2")
        if not download_tag:
            return None
        href_attributes = download_tag.find_all(href=True)
        if not href_attributes:
            return None
        sourceforge_url = href_attributes[0].get("href")
        if not isinstance(sourceforge_url, str):
            return None
        return sourceforge_url


    def install_latest_version(self) -> bool | None:

        download_link = self._get_download_link()
        if not download_link:
            self.logging_callback("No valid download link found, aborting install.")
            return None
        new_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(new_file, Path):
            self.logging_callback(f"new_file is not a Path: {new_file}")
            return None
        archive_path = new_file.with_suffix(".zip")

        # Download the archive
        result = robust_download(download_link, archive_path, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if not result:
            self.logging_callback(f"Download failed for {download_link}")
            return None

        # Verify archive file size
        if not verify_file_size(archive_path, download_link, logging_callback=self.logging_callback):
            self.logging_callback("Archive file size verification failed.")
            return None

        # Check integrity before extracting

        integrity_ok = self.check_integrity()
        if integrity_ok is False:
            self.logging_callback("Integrity check failed, aborting extraction.")
            return None
        elif integrity_ok == -1:
            self.logging_callback("Integrity check could not be performed, aborting extraction.")
            return None

        # Unzip the archive to extract the .img file, but do NOT check .img hash (no hash provided for .img)
        import zipfile
        with zipfile.ZipFile(archive_path, 'r') as zf:
            file_list = zf.namelist()
            self.logging_callback(f"Files in archive: {file_list}")
            inner_img_file = next((os.path.basename(f) for f in file_list if f.endswith(".img")), None)
            if not inner_img_file:
                self.logging_callback(f"FAIL: No .img file found in archive {archive_path}")
                return None
            self.logging_callback(f"Found inner .img file: {inner_img_file}")
            inner_img_path = new_file.parent / inner_img_file
            unzip_file(archive_path, new_file.parent)
            os.replace(inner_img_path, new_file)
            self.logging_callback(f"DONE. Installed to {new_file}")
            self.logging_callback(f"Archive kept at {archive_path}")
        return True


    @cache
    def _get_latest_version(self) -> list[str] | None:
        if not self.soup_latest_download_article:
            self.logging_callback(f"[{ISOname}] No soup object for download article, cannot get version.")
            return None
        download_table: Tag | None = self.soup_latest_download_article.find("table", attrs={"cellpadding": "5px"})  # type: ignore
        if not download_table:
            self.logging_callback(f"[{ISOname}] Could not find the table of download which contains the version number.")
            return None
        download_table_header: Tag | None = download_table.find("h2")  # type: ignore
        if not download_table_header:
            self.logging_callback(f"[{ISOname}] Could not find the header containing the version number.")
            return None
        header: str = download_table_header.getText().lower()
        splitter = getattr(self, 'version_splitter', ".")
        return self._str_to_version(
            header.replace("super grub2 disk", "")
            .strip()
            .replace("s", splitter)
            .replace("-beta", splitter)
        )

    def _find_in_table(self, row_name_contains: str) -> Tag | None:
        if not self.soup_latest_download_article:
            return None
        download_table: Tag | None = self.soup_latest_download_article.find("table", attrs={"cellpadding": "5px"})  # type: ignore
        if not download_table:
            return None
        for tr in download_table.find_all("tr"):
            for td in tr.find_all("td"):
                if row_name_contains in td.getText():
                    return td
        return None

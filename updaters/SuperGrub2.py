

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

    def check_integrity(self) -> bool | None:
        """
        Check the integrity of the downloaded archive (zip) if it exists.
        """
        new_file = self._get_complete_normalized_file_path(absolute=True)
        archive_path = new_file.with_suffix(".zip")
        if not archive_path.exists():
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No archive found for integrity check: {archive_path}")
            return None
        # Get hash info from soup
        if not self.soup_latest_download_article:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No soup object for download article, cannot check integrity.")
            return None
        sha256_sums_tag = self.soup_latest_download_article.find_all("pre")
        if not sha256_sums_tag:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Couldn't find the SHA256 sum for integrity check.")
            return None
        sha256_sums_tag = sha256_sums_tag[-1]
        sha256_checksums_str = sha256_sums_tag.getText()
        hash_lines = [line for line in sha256_checksums_str.splitlines() if "classic" not in line]
        filtered_hashes = "\n".join(hash_lines)
        archive_hash = parse_hash(filtered_hashes, ["-multiarch-USB.img.zip"], 0, logging_callback=self.logging_callback)
        if not archive_hash:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No hash found for archive in integrity check.")
            return None
        return sha256_hash_check(archive_path, archive_hash, logging_callback=self.logging_callback)

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
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No valid download link found, aborting install.")
            return None
        new_file = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(new_file, Path):
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] new_file is not a Path: {new_file}")
            return None
        archive_path = new_file.with_suffix(".zip")

        result = robust_download(download_link, archive_path, retries=self.retries_count, delay=1, logging_callback=self.logging_callback)
        if not result:
            return None

        if not verify_file_size(archive_path, download_link, package_name=ISOname, logging_callback=self.logging_callback):
            archive_path.unlink(missing_ok=True)
            return None

        if not self.soup_latest_download_article:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No soup object for download article, aborting install.")
            archive_path.unlink(missing_ok=True)
            return None

        # Only use hash lines not containing 'classic'
        # Check archive integrity using the shared method
        integrity_ok = self.check_integrity()
        if not integrity_ok:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] FAIL: Hash check failed or hash missing for {archive_path}.")
            archive_path.unlink(missing_ok=True)
            return None
        from updaters.shared.find_biggest_file_in_zip import find_biggest_file_in_zip
        to_extract = find_biggest_file_in_zip(str(archive_path), ext=".img")
        if not to_extract:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] FAIL: No .img file found in archive {archive_path}")
            archive_path.unlink(missing_ok=True)
            return None
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] Will extract: {to_extract}")
        import zipfile
        with zipfile.ZipFile(archive_path, 'r') as zf:
            zf.extract(to_extract, path=new_file.parent)
        extracted_path = new_file.parent / to_extract
        if not extracted_path.exists():
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] FAIL: No file found after unzip: {extracted_path}")
            archive_path.unlink(missing_ok=True)
            return None
        # Do not rename the extracted file; leave it as is
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] DONE. Extracted to {extracted_path}")
        return True


    @cache
    def _get_latest_version(self) -> list[str] | None:
        if not self.soup_latest_download_article:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] No soup object for download article, cannot get version.")
            return None
        download_table: Tag | None = self.soup_latest_download_article.find("table", attrs={"cellpadding": "5px"})  # type: ignore
        if not download_table:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not find the table of download which contains the version number.")
            return None
        download_table_header: Tag | None = download_table.find("h2")  # type: ignore
        if not download_table_header:
            if self.logging_callback:
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

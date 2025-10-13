

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

    def check_integrity(self) -> None:
        return None

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

        sha256_sums_tag = self.soup_latest_download_article.find_all("pre")
        if not sha256_sums_tag:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Couldn't find the SHA256 sum.")
            archive_path.unlink(missing_ok=True)
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] FAIL: No <pre> tag with SHA256 sum found in soup.")
            return None
        sha256_sums_tag = sha256_sums_tag[-1]
        sha256_checksums_str = sha256_sums_tag.getText()
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] SHA256 hash text from page:\n{sha256_checksums_str}")

        import zipfile
        with zipfile.ZipFile(archive_path, 'r') as zf:
            file_list = zf.namelist()
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] Files in archive: {file_list}")
        # Find the inner .img.zip file (just the filename, not path)
        inner_zip_file = next((os.path.basename(f) for f in file_list if f.endswith(".img")), None)
        if not inner_zip_file:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] FAIL: No .img file found in archive {archive_path}")
            archive_path.unlink(missing_ok=True)
            return None
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] Found inner .img.zip file: {inner_zip_file}")
        # Check hash for .img.zip
        img_zip_hash = parse_hash(sha256_checksums_str, [inner_zip_file], 0, logging_callback=self.logging_callback)
        inner_zip_path = new_file.parent / inner_zip_file
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] img_zip_hash for {inner_zip_file}: {img_zip_hash}")
        if not img_zip_hash or not sha256_hash_check(archive_path, img_zip_hash, logging_callback=self.logging_callback):
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] FAIL: Hash check failed or hash missing for {inner_zip_file}.")
            archive_path.unlink(missing_ok=True)
            inner_zip_path.unlink(missing_ok=True)
            return None
        # Unzip the .img.zip
        unzip_file(archive_path, new_file.parent)
        extracted_path = new_file.parent / inner_zip_path
        if not extracted_path:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] FAIL: No file found after inner unzip.")
            archive_path.unlink(missing_ok=True)
            return None
        archive_path.unlink(missing_ok=True)
        os.replace(extracted_path, new_file)
        if self.logging_callback:
            self.logging_callback(f"[{ISOname}] DONE. Installed to {new_file}")
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

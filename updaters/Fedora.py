from functools import cache
import re
from pathlib import Path
from bs4 import BeautifulSoup
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.check_remote_integrity import check_remote_integrity
from updaters.shared.verify_file_size import verify_file_size
from updaters.shared.robust_get import robust_get

DOMAIN = "https://fedoraproject.org"
DOWNLOAD_PAGE_URL = f"{DOMAIN}/spins/[[EDITION]]/download/"
FILE_NAME = "Fedora-[[EDITION]]-Live-x86_64-[[VER]].iso"
ISOname = "Fedora"




class Fedora(GenericUpdater):
    def __init__(self, folder_path: Path, edition: str, *args, **kwargs):
        self.valid_editions = [
            "Budgie", "Cinnamon", "KDE", "LXDE", "MATE_Compiz", "SoaS", "Sway", "Xfce", "i3"
        ]
        self.edition = edition
        file_name = FILE_NAME.replace("[[EDITION]]", self.edition)
        file_path = folder_path / file_name
        super().__init__(file_path, *args, **kwargs)
        self.edition = next(
            valid_ed for valid_ed in self.valid_editions if valid_ed.lower() == self.edition.lower()
        )
        url_edition = self.edition.lower() if self.edition != "MATE_Compiz" else "mate"
        self.download_page = robust_get(
            DOWNLOAD_PAGE_URL.replace("[[EDITION]]", url_edition),
            logging_callback=self.logging_callback
        )
        if not self.download_page or getattr(self.download_page, 'status_code', 0) != 200:
            if self.logging_callback:
                self.logging_callback(f"[Fedora] Failed to fetch the download page from '{getattr(self.download_page, 'url', 'unknown')}'")
            self.soup_download_page = BeautifulSoup("", features="html.parser")
        else:
            self.soup_download_page = BeautifulSoup(self.download_page.content.decode("utf-8"), features="html.parser")
            if self.logging_callback:
                page_title = self.soup_download_page.title.string.strip() if self.soup_download_page.title and self.soup_download_page.title.string else "(no title)"
                self.logging_callback(f"[Fedora] Initial download page: URL={getattr(self.download_page, 'url', 'unknown')}, Title={page_title}")
            meta = self.soup_download_page.find("meta", attrs={"http-equiv": "refresh"})
            if meta and "content" in meta.attrs:
                content = meta["content"]
                if not isinstance(content, str):
                    content = " ".join(content)
                if "url=" in content:
                    redirect_url = content.split("url=")[1].strip()
                    if redirect_url.startswith("/"):
                        redirect_url = DOMAIN + redirect_url
                    elif not redirect_url.startswith("http"):
                        redirect_url = DOMAIN + "/" + redirect_url
                    new_page = robust_get(redirect_url, logging_callback=self.logging_callback)
                    if new_page and getattr(new_page, 'status_code', 0) == 200:
                        self.soup_download_page = BeautifulSoup(new_page.content.decode("utf-8"), features="html.parser")
                        if self.logging_callback:
                            page_title = self.soup_download_page.title.string.strip() if self.soup_download_page.title and self.soup_download_page.title.string else "(no title)"
                            self.logging_callback(f"[Fedora] After meta-refresh: URL={getattr(new_page, 'url', 'unknown')}, Title={page_title}")

    @cache
    def _get_download_link(self) -> str | None:
        latest_version = self._get_latest_version()
        if not latest_version or not isinstance(latest_version, list) or not latest_version[0]:
            return None
        base_url = "https://download.fedoraproject.org/pub/fedora/linux/releases"
        # Use both major and minor if available
        if len(latest_version) > 1:
            major = latest_version[0]
            minor = latest_version[1]
            file_name = f"Fedora-{self.edition}-Desktop-Live-{major}-{minor}.x86_64.iso"
            url = f"{base_url}/{major}/{self.edition}/x86_64/iso/{file_name}"
        else:
            major = latest_version[0]
            file_name = f"Fedora-{self.edition}-Desktop-Live-{major}.x86_64.iso"
            url = f"{base_url}/{major}/{self.edition}/x86_64/iso/{file_name}"
        return url

    def check_integrity(self) -> bool | int | None:
        latest_version = self._get_latest_version()
        if not isinstance(latest_version, list):
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not determine latest version for edition: {self.edition}")
            return None
        local_file = self._get_complete_normalized_file_path(absolute=True)
        if not local_file.exists():
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] File does not exist: {local_file}")
            return False
        sha256_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{latest_version[0]}/{self.edition}/x86_64/iso/Fedora-{self.edition}-{latest_version[0]}-{latest_version[1]}{'.'+latest_version[2] if len(latest_version)>2 else ''}-x86_64-CHECKSUM"
        match_string = f"SHA256 (Fedora-{self.edition}"
        iso_url = self._get_download_link()
        if not iso_url:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Could not determine ISO download URL for file size check.")
            return None
        size_ok = verify_file_size(local_file, iso_url, self.logging_callback, ISOname)
        if not size_ok:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] File size check failed.")
            return False
        hash_ok = check_remote_integrity(
            hash_url=sha256_url,
            local_file=local_file,
            hash_type="sha256",
            parse_hash_args=([match_string], -1),
            logging_callback=self.logging_callback
        )
        if not hash_ok:
            if self.logging_callback:
                self.logging_callback(f"[{ISOname}] Hash check failed.")
            return False
        return True

    @cache
    def _get_latest_version(self) -> list[str] | None:
        # Try to find any anchor tag with .iso in href
        iso_link = None
        for a in self.soup_download_page.find_all("a", href=True):
            href = str(a["href"])
            if href.endswith(".iso") and "Live" in href and self.edition.lower() in href.lower():
                iso_link = href
                break
        if not iso_link:
            if self.logging_callback:
                self.logging_callback(f"[Fedora] Could not find ISO link. Edition: {self.edition}")
            return None
        m = re.search(r"Live-(\d+)-(\d+\.\d+)\.x86_64\.iso", str(iso_link))
        if not m:
            #m = re.search(r"Live-(\d+)\.x86_64\.iso", str(iso_link))
            #if not m:
                if self.logging_callback:
                    self.logging_callback(f"[Fedora] Could not extract version from ISO link: {iso_link}")
                return None
        else:
            # Return as a list of strings to match the base class signature
            version = [m.group(1), m.group(2)]
        return version
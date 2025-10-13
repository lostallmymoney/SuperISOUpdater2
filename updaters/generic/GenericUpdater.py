from abc import ABC
from pathlib import Path
from functools import cache
import glob
import re
# Import all shared updater functions (absolute imports for compatibility)
from updaters.shared.robust_download import robust_download
from updaters.shared.sha256_hash_check import sha256_hash_check
from updaters.shared.fetch_hashes_from_url import fetch_hashes_from_url


class GenericUpdater(ABC):
    # --- Begin inlined shared functions ---

    def _get_local_file(self) -> Path | None:
        normalized_path = self._get_normalized_file_path(absolute=True)
        local_files = glob.glob(str(normalized_path).replace("[[VER]]", "*"))
        if local_files:
            return Path(local_files[0])
        return None
    
    def _get_local_version(self) -> list[str] | None:
        local_version: list[str] | None = None
        local_file = self._get_local_file()
        if local_file is None or not self.has_version():
            return None
        local_file_without_ext = local_file.with_suffix("")
        normalized_path_without_ext = self._get_normalized_file_path(
            absolute=True
        ).with_suffix("")
        version_regex: str = r"(.+)".join(
            re.escape(part)
            for part in str(normalized_path_without_ext).split("[[VER]]")
        )
        local_version_regex = re.search(version_regex, str(local_file_without_ext))
        if local_version_regex:
            local_version = self._str_to_version(local_version_regex.group(1))
        return local_version
    
    def _version_to_str(self, version: list[str]) -> str:
        return self.version_splitter.join(str(i) for i in version)

    def _str_to_version(self, version_str: str) -> list[str]:
        return [
        version_number.strip()
        for version_number in version_str.split(self.version_splitter)
    ]

    def check_integrity(self) -> bool | int | None:
        """
        Default integrity check using sha256_hash_check. Updaters can override for custom logic.
        Returns:
            True if integrity passes, False if fails, -1 if unavailable, None if inconclusive.
        """
        # Determine the file to check
        local_file = self._get_complete_normalized_file_path(absolute=True) if getattr(self, 'file_path', None) is None else self.file_path
        if getattr(self, 'file_path', None) is None and local_file == -1:
            return -1
        # Get the download link (for hash source)
        download_link = self._get_download_link()
        if download_link is None:
            return -1
        # Fetch hashes from the download link (or override in subclass)
        hashes = fetch_hashes_from_url(download_link)
        if not hashes:
            if self.logging_callback:
                self.logging_callback("No hash value provided for integrity check.")
            return -1
        # Get the file path to check
        file_to_check = self._get_complete_normalized_file_path(absolute=True)
        if not isinstance(file_to_check, Path):
            return -1
        # Run the hash check
        return sha256_hash_check(
            file_to_check,
            hashes,
            package_name=getattr(self, 'ISOname', ''),
            logging_callback=self.logging_callback
        )
    """
    Abstract base class for a generic updater that manages software updates.
    Attributes:
        file_path (Path): The path to the file that needs to be updated.
    """

    def __init__(self, file_path: Path, *args, logging_callback, **kwargs) -> None:
        self.file_path = file_path.resolve()
        self.folder_path = file_path.parent.resolve()
        self.version_splitter = "."
        self.logging_callback = logging_callback
        # Store retries_count if present in kwargs, else default to 0
        self.retries_count = kwargs.get('retries_count', 0)
        # NOTE: Updaters should handle logging via callback if needed. Base class does not log.
        if self.has_edition() and hasattr(self, 'valid_editions'):
            edition = getattr(self, 'edition', None)
            if isinstance(edition, str):
                if edition.lower() not in (
                    valid_edition.lower() for valid_edition in self.valid_editions  # type: ignore
                ):
                    raise ValueError(
                        f"Invalid edition. The available editions are: {', '.join(self.valid_editions)}."  # type: ignore
                    )
        if self.has_lang() and hasattr(self, 'valid_langs'):
            lang = getattr(self, 'lang', None)
            if isinstance(lang, str):
                if lang.lower() not in (
                    valid_lang.lower() for valid_lang in self.valid_langs  # type: ignore
                ):
                    raise ValueError(
                        f"Invalid language. The available languages are: {', '.join(self.valid_langs)}."  # type: ignore
                    )
        self.folder_path.mkdir(parents=True, exist_ok=True)




    def has_version(self) -> bool:
        return "[[VER]]" in str(self.file_path)

    def has_edition(self) -> bool:
        return (
            hasattr(self, "edition")
            and hasattr(self, "valid_editions")
            and "[[EDITION]]" in str(self.file_path)
        )

    def has_lang(self) -> bool:
        return (
            hasattr(self, "lang")
            and hasattr(self, "valid_langs")
            and "[[LANG]]" in str(self.file_path)
        )




    
    def _get_normalized_file_path(
        self,
        absolute: bool,
        version: list[str] | None = None,
        edition: str | None = None,
        lang: str | None = None,
    ) -> Path:
        file_name: str = self.file_path.name
        # Replace placeholders with the specified version, edition, and language
        if version is not None and "[[VER]]" in file_name:
            file_name = file_name.replace("[[VER]]", self._version_to_str(version))
        if edition is not None and "[[EDITION]]" in file_name:
            file_name = file_name.replace("[[EDITION]]", edition)
        if lang is not None and "[[LANG]]" in file_name:
            file_name = file_name.replace("[[LANG]]", lang)
        file_name = "".join(file_name.split())
        return self.folder_path / file_name if absolute else Path(file_name)


    def _get_complete_normalized_file_path(
        self, absolute: bool, latest: bool = True
    ) -> Path:
        return self._get_normalized_file_path(
            absolute=absolute,
            version=self._get_latest_version() if latest else self._get_local_version(),
            edition=getattr(self, 'edition', None) if self.has_edition() else None,
            lang=getattr(self, 'lang', None) if self.has_lang() else None,
        )
    


    def check_for_updates(self) -> bool | int | None:
        # Only integrity matters: update if integrity fails, skip if it passes
        try:
            integrity_ok = self.check_integrity()
        except Exception as e:
            if self.logging_callback:
                self.logging_callback(f"[{getattr(self, 'ISOname', self.__class__.__name__)}] Integrity check error: {e}")
            integrity_ok = -1

        if integrity_ok == -1:
            if self.logging_callback:
                self.logging_callback(f"[{getattr(self, 'ISOname', self.__class__.__name__)}] Integrity check unavailable. Skipping update.")
            return -1
        elif integrity_ok is None:
            if self.logging_callback:
                self.logging_callback(f"[{getattr(self, 'ISOname', self.__class__.__name__)}] Integrity check inconclusive. Assuming update needed.")
            return None
        elif integrity_ok:
            if self.logging_callback:
                self.logging_callback(f"[{getattr(self, 'ISOname', self.__class__.__name__)}] Local file passed integrity check. No update needed.")
            return False
        else:
            if self.logging_callback:
                self.logging_callback(f"[{getattr(self, 'ISOname', self.__class__.__name__)}] Integrity check failed or file missing. Update required.")
            return True



    def install_latest_version(self) -> None | bool:
        """
        Install the latest version of the software.

        Returns:
            True on success, None or False on failure.
        """
        download_link = self._get_download_link()
        old_file = self._get_local_file()
        new_file = self._get_complete_normalized_file_path(absolute=True)
        has_version_fn = self.has_version
        retries = self.retries_count
        logging_callback = self.logging_callback

        if not has_version_fn():
            if old_file:
                if logging_callback:
                    logging_callback(f"[GenericUpdater.install_latest_version] Renaming old file: {old_file}")
                old_file.with_suffix(".old").replace(old_file)

        def resolve_placeholder(val, fallback=None):
            if val is None:
                return fallback or ""
            if isinstance(val, (list, tuple)):
                return ".".join(str(x) for x in val)
            return str(val)

        version = None
        edition = None
        lang = None
        if hasattr(new_file, 'name'):
            m = re.search(r'(\\d+\\.\\d+(?:\\.\\d+)*)', new_file.name)
            if m:
                version = m.group(1)

        # Replace placeholders in download_link
        if isinstance(download_link, str):
            if '[[VER]]' in download_link and version:
                download_link = download_link.replace('[[VER]]', resolve_placeholder(version))
            if '[[EDITION]]' in download_link and edition:
                download_link = download_link.replace('[[EDITION]]', resolve_placeholder(edition))
            if '[[LANG]]' in download_link and lang:
                download_link = download_link.replace('[[LANG]]', resolve_placeholder(lang))
            if any(ph in download_link for ph in ['[[VER]]', '[[EDITION]]', '[[LANG]]']):
                if logging_callback:
                    logging_callback(f"[install_latest_version] ERROR: Unresolved placeholder(s) in download_link: {download_link}")
                return None

        # Replace placeholders in new_file path (if Path)
        if hasattr(new_file, 'name') and isinstance(new_file.name, str):
            new_name = new_file.name
            if '[[VER]]' in new_name and version:
                new_name = new_name.replace('[[VER]]', resolve_placeholder(version))
            if '[[EDITION]]' in new_name and edition:
                new_name = new_name.replace('[[EDITION]]', resolve_placeholder(edition))
            if '[[LANG]]' in new_name and lang:
                new_name = new_name.replace('[[LANG]]', resolve_placeholder(lang))
            if any(ph in new_name for ph in ['[[VER]]', '[[EDITION]]', '[[LANG]]']):
                if logging_callback:
                    logging_callback(f"[install_latest_version] ERROR: Unresolved placeholder(s) in new_file: {new_name}")
                return None
            if new_name != new_file.name:
                new_file = new_file.with_name(new_name)

        attempt = 0
        max_attempts = float('inf') if retries == -1 else max(1, retries)
        while True:
            attempt += 1
            if logging_callback:
                logging_callback(f"[install_latest_version] Download attempt {attempt} for {download_link}")
            if download_link is None:
                if logging_callback:
                    logging_callback(f"[install_latest_version] ERROR: No download link provided, cannot proceed with download.")
                return None
            if logging_callback:
                logging_callback(f"[install_latest_version] Starting robust_download for {download_link}")
            resp = robust_download(download_link, local_file=new_file, retries=1, delay=1, logging_callback=logging_callback)
            if logging_callback:
                logging_callback(f"[install_latest_version] robust_download finished for {download_link} (resp type: {type(resp)}, status: {resp})")
            if resp is not True:
                if logging_callback:
                    logging_callback(f"[install_latest_version] Download failed (attempt {attempt}) for {download_link}")
                if attempt >= max_attempts:
                    if logging_callback:
                        logging_callback(f"[install_latest_version] Exceeded max download attempts for {download_link}")
                    return None
                continue
            if logging_callback:
                logging_callback(f"[install_latest_version] File written to {new_file}, starting integrity check...")
            break

        return True



    @cache
    def _get_download_link(self) -> str | None:
        """
        (Protected) Get the download link for the latest version of the software.

        Returns:
            str: The download link for the latest version of the software.
        """
        return "http://www.google.com/"

    @cache
    def _get_latest_version() -> list[str] | None:
        return None

    def _compare_version_numbers(self,
            old_version: list[str], new_version: list[str]
        ) -> bool:
            """
            Compare version numbers to check if a new version is available.

            Args:
                old_version (list[str]): The old version as a list of version components.
                new_version (list[str]): The new version as a list of version components.

            Returns:
                bool: True if the new version is greater than the old version, False otherwise.
            """
            for i in range(len(new_version)):
                try:
                    if int(new_version[i]) > int(old_version[i]):
                        return True
                except ValueError:
                    if int(new_version[i], 32) > int(old_version[i], 32):
                        return True
                except IndexError:
                    return True
            return False
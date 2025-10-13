import re
import uuid
from datetime import datetime

from updaters.shared.robust_get import robust_get


class WindowsConsumerDownloader:
    """
    A class to obtain a Windows ISO download URL for a specific Windows version and language.
    """

    _SESSION_ID = uuid.uuid4()
    _PROFILE_ID = "606624d44113"
    _ORG_ID = "y6jn8c31"

    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "referer": "localhost",
    }

    _session_authorized = False
    _download_page_cache = {}
    _language_skuIDs_cache = {}
    _download_link_cache = {}

    @staticmethod
    def windows_consumer_file_hash(windows_version: str, lang: str) -> str:
        """
        Obtain a Windows ISO download URL for a specific Windows version and language.

        Args:
            windows_version (str): The desired Windows version. Valid options are '11', '10', or '8'.
                                Default is '11'.
            lang (str): The desired language for the Windows ISO. Default is 'English International'.
                See https://www.microsoft.com/en-us/software-download/windows11 for a list of available languages

        Returns:
            str: Download link for the given Windows version and language
        """
        matches = re.search(
            rf"FileHash(.+\n+)+?^<\/tr>.+{lang}.+\n<td>(.+)<",
            WindowsConsumerDownloader._get_download_page(windows_version),
            re.MULTILINE,
        )

        if not matches or not matches.groups():
            raise LookupError("Could not find SHA256 hash")

        file_hash = matches.group(2)
        return file_hash

    @staticmethod
    def _get_download_page(windows_version: str) -> str:
        match windows_version:
            case "11":
                url_segment = f"windows{windows_version}"
            case "10" | "8":
                url_segment = f"windows{windows_version}ISO"
            case _:
                raise NotImplementedError(
                    "The valid Windows versions are '11', '10', or '8'."
                )

        if not url_segment in WindowsConsumerDownloader._download_page_cache:
            resp = robust_get(
                f"https://www.microsoft.com/en-us/software-download/{url_segment}",
                headers=WindowsConsumerDownloader._HEADERS,
                retries=3,
                delay=1,
            )
            if resp is None or getattr(resp, 'status_code', 200) != 200:
                raise RuntimeError(
                    f"Could not load the Windows {windows_version} download page."
                )
            WindowsConsumerDownloader._download_page_cache[url_segment] = resp.text

        return WindowsConsumerDownloader._download_page_cache[url_segment]

    @staticmethod
    def windows_consumer_download(windows_version: str, lang: str, logging_callback=None) -> str:
        """
        Obtain a Windows ISO download URL for a specific Windows version and language.

        Args:
            windows_version (str): The desired Windows version. Valid options are '11', '10', or '8'.
                                Default is '11'.
            lang (str): The desired language for the Windows ISO. Default is 'English International'.
                See https://www.microsoft.com/en-us/software-download/windows11 for a list of available languages
            logging_callback (callable, optional): A function to call with log messages.

        Returns:
            str: Download link for the given Windows version and language
        """
        def log(msg):
            if logging_callback:
                logging_callback(msg)

        matches = re.search(
            r'<option value="([0-9]+)">Windows',
            WindowsConsumerDownloader._get_download_page(windows_version),
        )
        if not matches or not matches.groups():
            raise LookupError("Could not find product edition id")

        product_edition_id = matches.group(1)
        log(f"[windows_consumer_download] Product edition id: `{product_edition_id}`")

        if not WindowsConsumerDownloader._session_authorized:
            robust_get(
                f"https://vlscppe.microsoft.com/tags?org_id={WindowsConsumerDownloader._ORG_ID}&session_id={WindowsConsumerDownloader._SESSION_ID}",
                retries=3,
                delay=1,
                logging_callback=logging_callback,
            )
            WindowsConsumerDownloader._session_authorized = True

        if product_edition_id not in WindowsConsumerDownloader._language_skuIDs_cache:
            language_skuIDs_url = (
                "https://www.microsoft.com/software-download-connector/api/getskuinformationbyproductedition"
                + f"?profile={WindowsConsumerDownloader._PROFILE_ID}"
                + f"&productEditionId={product_edition_id}"
                + f"&SKU=undefined"
                + f"&friendlyFileName=undefined"
                + f"&Locale=en-US"
                + f"&sessionID={WindowsConsumerDownloader._SESSION_ID}"
            )
            # concise log only
            log(f"[windows_consumer_download] Fetching SKU info")
            resp = robust_get(
                language_skuIDs_url,
                headers=WindowsConsumerDownloader._HEADERS,
                retries=3,
                delay=1,
                logging_callback=logging_callback,
            )
            if resp is None or getattr(resp, 'status_code', 200) != 200:
                log("[windows_consumer_download] Could not fetch SKU info (no response or bad status)")
                raise ValueError("Could not fetch SKU IDs")
            # Keep only concise status and count information to avoid large dump
            log(f"[windows_consumer_download] SKU info HTTP status: {getattr(resp, 'status_code', 'NO STATUS')}")
            language_skuIDs = resp.json()
            try:
                sku_count = len(language_skuIDs.get("Skus", []))
            except Exception:
                sku_count = "unknown"
            log(f"[windows_consumer_download] SKU info received, skus={sku_count}")
            if not "Skus" in language_skuIDs:
                log(f"[windows_consumer_download] SKU JSON: {language_skuIDs}")
                raise ValueError("Could not find SKU IDs")
            WindowsConsumerDownloader._language_skuIDs_cache[product_edition_id] = language_skuIDs

        language_skuIDs = WindowsConsumerDownloader._language_skuIDs_cache[
            product_edition_id
        ]

        sku_id = None
        # Find matching SKU by language; avoid logging entire SKU list to reduce noise
        for sku in language_skuIDs.get("Skus", []):
            if sku.get("Language") == lang:
                sku_id = sku.get("Id")
                break
        if sku_id:
            log(f"[windows_consumer_download] Matched SKU ID: {sku_id}")

        if not sku_id:
            log(f"[windows_consumer_download] No SKU found for language: {lang}")
            raise ValueError(f"The language '{lang}' for Windows could not be found!")

        log(f"[windows_consumer_download] Found SKU ID {sku_id} for {lang}")

        if (
            sku_id not in WindowsConsumerDownloader._download_link_cache
            or datetime.now()
            < WindowsConsumerDownloader._download_link_cache[sku_id]["expires"]
        ):
            # Get ISO download link page
            iso_download_link_page = (
                "https://www.microsoft.com/software-download-connector/api/GetProductDownloadLinksBySku"
                + f"?profile={WindowsConsumerDownloader._PROFILE_ID}"
                + "&productEditionId=undefined"
                + f"&SKU={sku_id}"
                + "&friendlyFileName=undefined"
                + f"&Locale=en-US"
                + f"&sessionID={WindowsConsumerDownloader._SESSION_ID}"
            )
            log(f"[windows_consumer_download] Fetching ISO download link from: {iso_download_link_page}")
            resp = robust_get(
                iso_download_link_page,
                headers=WindowsConsumerDownloader._HEADERS,
                retries=3,
                delay=1,
                logging_callback=logging_callback,
            )
            if resp is None or getattr(resp, 'status_code', 200) != 200:
                log(f"[windows_consumer_download] Could not fetch ISO download link page, status: {getattr(resp, 'status_code', 'NO STATUS')}")
                raise RuntimeError("Could not fetch ISO download link page")
            iso_download_link_json = resp.json()
            if "Errors" in iso_download_link_json:
                log(f"[windows_consumer_download] Errors from Microsoft: {iso_download_link_json['Errors']}")
                raise RuntimeError(
                    f"Errors from Microsoft: {iso_download_link_json['Errors']}"
                )
            # Find the x64 ISO link in ProductDownloadOptions
            x64_option = None
            for option in iso_download_link_json.get("ProductDownloadOptions", []):
                uri = option.get("Uri", "")
                # Heuristic: look for x64 in the filename or URL
                if "x64" in uri.lower():
                    x64_option = option
                    break
            if not x64_option:
                # Fallback: just use the first option, but log a warning
                log("[windows_consumer_download] WARNING: Could not find x64 ISO, using first available option!")
                x64_option = iso_download_link_json["ProductDownloadOptions"][0]
            WindowsConsumerDownloader._download_link_cache[sku_id] = {
                "expires": datetime.strptime(
                    iso_download_link_json["DownloadExpirationDatetime"][:-2],
                    "%Y-%m-%dT%H:%M:%S.%f",
                ),
                "link": x64_option["Uri"],
            }

        download_link = WindowsConsumerDownloader._download_link_cache[sku_id]["link"]
        log(f"[windows_consumer_download] Selected download link: {download_link}")
        return download_link

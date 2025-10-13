from pathlib import Path
from updaters.shared.fetch_expected_file_size import fetch_expected_file_size as fetch_expected_file_size

def verify_file_size(file_path: Path, download_link: str, logging_callback, package_name: str = "") -> bool:
    """
    Verifies the file size of a local file against the expected size from the download link.
    Returns True if the file exists and the size matches, False otherwise.
    """
    if file_path.exists():
        expected_size = fetch_expected_file_size(download_link)
        if expected_size is None:
            msg = f"[{package_name}] Could not fetch file size from link: {download_link}"
            if logging_callback:
                logging_callback(msg)
            return False
        actual_size = file_path.stat().st_size
        if logging_callback:
            logging_callback(f"[{package_name}] Expected file size: {expected_size}, File size: {actual_size} (file: {file_path})")
        if actual_size != expected_size:
            if logging_callback:
                logging_callback(f"[{package_name}] File size mismatch, will redownload.")
            return False
        return True
    
    logging_callback(f"[{package_name}] File: {file_path} does NOT exists.")
    return False

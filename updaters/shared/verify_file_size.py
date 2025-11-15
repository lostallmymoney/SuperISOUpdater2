from updaters.shared.resolve_file_case import resolve_file_case
from pathlib import Path
from pathlib import Path
from updaters.shared.fetch_expected_file_size import fetch_expected_file_size as fetch_expected_file_size

def verify_file_size(file_path: Path, download_link: str, logging_callback) -> bool:
    """
    Verifies the file size of a local file against the expected size from the download link.
    Returns True if the file exists and the size matches, False otherwise.
    """
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    local_file = resolve_file_case(file_path)
    if local_file:
        expected_size = fetch_expected_file_size(download_link, logging_callback)
        if expected_size is None:
            msg = f"{RED}Could not fetch file size from link: {download_link}{RESET}"
            logging_callback(msg)
            return False
        actual_size = local_file.stat().st_size
        logging_callback(f"Expected file size: {expected_size}, File size: {actual_size} (file: {local_file})")
        if actual_size != expected_size:
            logging_callback(f"{RED}File size mismatch, will redownload.{RESET}")
            return False
        return True
    
    logging_callback(f"{RED}File: {file_path} does NOT exists.{RESET}")
    return False

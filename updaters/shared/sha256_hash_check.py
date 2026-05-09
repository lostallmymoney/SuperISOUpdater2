from pathlib import Path
from updaters.shared.resolve_file_case import resolve_file_case
import hashlib

READ_CHUNK_SIZE = 8 * 1024 * 1024

def hash_check(file: Path, hash_value: str, logging_callback, hash_type: str = "sha256") -> bool:
    """
    Calculate the hash of a given file and compare it with a provided hash value.
    Supports 'sha256', 'sha1', 'md5', etc.
    """
    local_file = resolve_file_case(file)
    if not local_file:
        logging_callback(f"[hash_check] File not found for hash check: {file}")
        return False
    try:
        h = getattr(hashlib, hash_type)()
    except AttributeError:
        logging_callback(f"[hash_check] Unsupported hash type: {hash_type}")
        return False

    with open(local_file, "rb") as f:
        bytes_done = 0
        log_interval = 500 * 1024 * 1024
        next_log_bytes = log_interval
        while True:
            chunk = f.read(READ_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
            bytes_done += len(chunk)
            if bytes_done >= next_log_bytes:
                logging_callback(f"Hashing: {bytes_done // (1024 * 1024):,} MB hashed...")
                next_log_bytes += log_interval

    file_hash = h.hexdigest()
    result = hash_value.lower() == file_hash
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'
    if result:
        logging_callback(f"{GREEN}{hash_type.upper()} check: OK (expected {hash_value.lower()}, got {file_hash}){RESET}")
    else:
        logging_callback(f"{RED}{hash_type.upper()} check: FAILED (expected {hash_value.lower()}, got {file_hash}){RESET}")
    return result



def sha256_hash_check(file: Path, hash: str, logging_callback) -> bool:
    """
    SHA-256 hash check wrapper using logging_callback for progress.
    """
    return hash_check(file, hash, hash_type="sha256", logging_callback=logging_callback)

import hashlib
from pathlib import Path

READ_CHUNK_SIZE = 524288

def hash_check(file: Path, hash_value: str, package_name: str = "", hash_type: str = "sha256", logging_callback=None) -> bool:
    """
    Calculate the hash of a given file and compare it with a provided hash value.
    Supports 'sha256', 'sha1', 'md5', etc.
    """
    if not package_name:
        package_name = file.stem if hasattr(file, 'stem') else str(file)
    h = getattr(hashlib, hash_type)()
    with open(file, "rb") as f:
        chunk_count = 0
        mb_interval = 500
        mb_per_chunk = READ_CHUNK_SIZE / (1024*1024)
        next_log_mb = mb_interval
        while True:
            chunk = f.read(READ_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
            chunk_count += 1
            if logging_callback:
                mb_done = chunk_count * mb_per_chunk
                if mb_done >= next_log_mb:
                    logging_callback(f"[{package_name}] Hashing: {int(mb_done):,} MB hashed...")
                    next_log_mb += mb_interval
        if logging_callback:
            logging_callback("")  # Clear progress line
    file_hash = h.hexdigest()
    result = hash_value.lower() == file_hash
    if logging_callback:
        logging_callback(f"[{package_name}] {hash_type.upper()} check: {'OK' if result else 'FAILED'} (expected {hash_value.lower()}, got {file_hash})")
    return result


def sha256_hash_check(file: Path, hash: str, package_name: str = "", logging_callback=None) -> bool:
    """
    SHA-256 hash check wrapper using logging_callback for progress.
    """
    return hash_check(file, hash, hash_type="sha256", package_name=package_name, logging_callback=logging_callback)


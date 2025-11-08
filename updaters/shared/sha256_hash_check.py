import hashlib
from pathlib import Path

READ_CHUNK_SIZE = 524288

def hash_check(file: Path, hash_value: str, logging_callback, hash_type: str = "sha256") -> bool:
    """
    Calculate the hash of a given file and compare it with a provided hash value.
    Supports 'sha256', 'sha1', 'md5', etc.
    """
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
            mb_done = chunk_count * mb_per_chunk
            if mb_done >= next_log_mb:
                logging_callback(f"Hashing: {int(mb_done):,} MB hashed...")
                next_log_mb += mb_interval
    # Only clear progress line if a non-empty message is needed
    # (skip empty log to avoid empty log lines)
    pass
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


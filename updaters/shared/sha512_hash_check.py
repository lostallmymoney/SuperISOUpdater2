import hashlib
from pathlib import Path

READ_CHUNK_SIZE = 524288

def sha512_hash_check(file: Path, hash: str, logging_callback) -> bool:
    """
    Calculate the SHA-512 hash of a given file and compare it with a provided hash value.
    """
    with open(file, "rb") as f:
        file_hash = hashlib.sha512()
        while chunk := f.read(READ_CHUNK_SIZE):
            file_hash.update(chunk)
    result = hash.lower() == file_hash.hexdigest()
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'
    if result:
        logging_callback(f"{GREEN}SHA512 check: OK (expected {hash.lower()}, got {file_hash.hexdigest()}){RESET}")
    else:
        logging_callback(f"{RED}SHA512 check: FAILED (expected {hash.lower()}, got {file_hash.hexdigest()}){RESET}")
    return result

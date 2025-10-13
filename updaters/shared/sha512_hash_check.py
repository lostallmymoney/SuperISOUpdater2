import hashlib
from pathlib import Path

READ_CHUNK_SIZE = 524288

def sha512_hash_check(file: Path, hash: str, logging_callback=None) -> bool:
    """
    Calculate the SHA-512 hash of a given file and compare it with a provided hash value.
    """
    with open(file, "rb") as f:
        file_hash = hashlib.sha512()
        while chunk := f.read(READ_CHUNK_SIZE):
            file_hash.update(chunk)
    result = hash.lower() == file_hash.hexdigest()
    if logging_callback:
        logging_callback(f"[sha512_hash_check] check: {'OK' if result else 'FAILED'} (expected {hash.lower()}, got {file_hash.hexdigest()})")
    return result

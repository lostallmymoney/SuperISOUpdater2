from pathlib import Path
from updaters.shared.sha256_hash_check import hash_check

def sha512_hash_check(file: Path, hash: str, logging_callback) -> bool:
    """
    Calculate the SHA-512 hash of a given file and compare it with a provided hash value.
    """
    return hash_check(file, hash, hash_type="sha512", logging_callback=logging_callback)

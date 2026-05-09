from pathlib import Path
from updaters.shared.sha256_hash_check import hash_check

def md5_hash_check(file: Path, hash: str, logging_callback) -> bool:
    """
    Calculate the MD5 hash of a given file and compare it with a provided hash value.
    Optionally include isoname in the log message.
    """
    return hash_check(file, hash, hash_type="md5", logging_callback=logging_callback)

import pgpy
import mmap
from pathlib import Path
from typing import Union

def verify_tails_mmap_bytes(file_path: Path, sig_data: bytes, key_data: bytes, logging_callback=None) -> bool:
    """
    Verify a Tails ISO using a memory-mapped ISO, a signature in bytes, and a PGP key in bytes or string.

    Args:
        iso_mmap: Memory-mapped ISO file (mmap.mmap).
        sig_data: Detached signature as bytes.
        key_data: PGP signing key as bytes or ASCII-armored string.

    Returns:
        True if verification succeeds.

    Raises:
        ValueError if signature verification fails.
    """

    # Load the PGP signing key from bytes or string
    if isinstance(key_data, bytes):
        key_str = key_data.decode('utf-8')
    else:
        key_str = key_data
    key_obj = pgpy.PGPKey.from_blob(key_str)
    key = key_obj[0] if isinstance(key_obj, tuple) else key_obj

    # Load the detached signature from bytes
    sig = pgpy.PGPSignature.from_blob(sig_data)

    # Open and memory-map the ISO file
    with open(str(file_path), "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as file_mmap:
            if not key.verify(file_mmap[:], sig):
                raise ValueError("ISO signature verification failed!")
    return True

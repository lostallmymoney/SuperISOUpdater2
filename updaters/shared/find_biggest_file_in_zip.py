from zipfile import ZipFile
from typing import Optional
import os

def find_biggest_file_in_zip(zip_path: str, ext: str) -> Optional[str]:
    """
    Returns the filename of the largest file in the zip archive at zip_path that ends with ext (case-insensitive).
    Returns None if no such file is found.
    """
    biggest = None
    biggest_size = -1
    with ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            if info.filename.lower().endswith(ext.lower()):
                if info.file_size > biggest_size:
                    biggest = info.filename
                    biggest_size = info.file_size
    return biggest

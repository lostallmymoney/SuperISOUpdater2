import zipfile
from pathlib import Path
from typing import Union

def list_zip_files(src: Union[str, Path]) -> list[str]:
    """
    List all files in a zip archive.
    Args:
        src (str | Path): Path to the zip file.
    Returns:
        list[str]: List of file names in the archive.
    """
    src_path = Path(src)
    with zipfile.ZipFile(src_path, 'r') as zip_ref:
        return zip_ref.namelist()

import zipfile
from pathlib import Path
from typing import Union

def unzip_file(src: Union[str, Path], dest: Union[str, Path]) -> None:
    """
    Unzip a zip file from src to dest.
    Args:
        src (str | Path): Path to the zip file.
        dest (str | Path): Path to the destination directory.
    """
    src_path = Path(src)
    dest_path = Path(dest)
    with zipfile.ZipFile(src_path, 'r') as zip_ref:
        zip_ref.extractall(dest_path)



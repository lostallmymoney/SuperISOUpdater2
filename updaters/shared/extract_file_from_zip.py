import zipfile
from pathlib import Path
from typing import Union

def extract_file_from_zip(src: Union[str, Path], member: str, dest: Union[str, Path]) -> bool:
    try:
        src_path = Path(src)
        dest_path = Path(dest)
        with zipfile.ZipFile(src_path, 'r') as zip_ref:
            zip_ref.extract(member, path=dest_path)
        return True
    except Exception:
        return False

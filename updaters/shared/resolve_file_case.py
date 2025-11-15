from pathlib import Path
from typing import Optional

def resolve_file_case(file: Path) -> Optional[Path]:
    """
    Try the original, lowercase, and uppercase extensions for a file.
    Returns the first Path that exists, or None if not found.
    """
    if file.exists():
        return file
    lower = file.with_suffix(file.suffix.lower())
    if lower != file and lower.exists():
        return lower
    upper = file.with_suffix(file.suffix.upper())
    if upper != file and upper.exists():
        return upper
    return None

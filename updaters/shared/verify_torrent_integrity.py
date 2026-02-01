

import os
from pathlib import Path

# Minimal bdecode implementation (no external dependencies)
def bdecode(data):
    def decode_item(index):
        if isinstance(data, (bytes, bytearray)):
            get = lambda i: data[i]
        else:
            raise TypeError('data must be bytes or bytearray')
        if get(index) == ord('i'):
            index += 1
            end = data.index(b'e', index)
            number = int(data[index:end])
            return number, end + 1
        elif get(index) == ord('l'):
            index += 1
            lst = []
            while get(index) != ord('e'):
                item, index = decode_item(index)
                lst.append(item)
            return lst, index + 1
        elif get(index) == ord('d'):
            index += 1
            dct = {}
            while get(index) != ord('e'):
                key, index = decode_item(index)
                val, index = decode_item(index)
                dct[key] = val
            return dct, index + 1
        elif chr(get(index)).isdigit():
            colon = data.index(b':', index)
            length = int(data[index:colon])
            start = colon + 1
            end = start + length
            return data[start:end], end
        else:
            raise ValueError('Invalid bencode')
    result, _ = decode_item(0)
    return result

def get_torrent_info(torrent_path):
    """
    Parse a .torrent file and return info dict and file list with sizes using minimal bdecode.
    """
    if not Path(torrent_path).exists():
        # Torrent file missing, return False
        return False
    with open(torrent_path, 'rb') as f:
        torrent = bdecode(f.read())
    # Support both bytes and str keys for compatibility
    def get(d, key):
        if key in d:
            return d[key]
        if isinstance(key, bytes):
            try:
                return d[key.decode('utf-8')]
            except Exception:
                pass
        elif isinstance(key, str):
            try:
                return d[key.encode('utf-8')]
            except Exception:
                pass
        raise KeyError(key)

    info = get(torrent, 'info')
    files = []
    if 'files' in info or b'files' in info:
        # Multi-file torrent
        for file in get(info, 'files'):
            length = get(file, 'length')
            path = b'/'.join(get(file, 'path')) if b'path' in file or 'path' in file else b''
            path = path.decode('utf-8') if isinstance(path, bytes) else str(path)
            files.append({'path': path, 'length': length})
    else:
        # Single file torrent
        name = get(info, 'name')
        name = name.decode('utf-8') if isinstance(name, bytes) else str(name)
        length = get(info, 'length')
        files.append({'path': name, 'length': length})
    return info, files

def verify_torrent_integrity(torrent_path, download_dir):
    """
    Verify that all files described in the torrent exist in download_dir and match the expected size.
    Returns True if all files are present and correct, False otherwise.
    """
    result = get_torrent_info(torrent_path)
    if result is False:
        print(f"[verify_torrent_integrity] Torrent file missing: {torrent_path}")
        return False
    info, files = result
    all_ok = True
    for file in files:
        # Normalize path for cross-platform compatibility
        rel_path = file['path'].replace('\\', os.sep).replace('/', os.sep)
        file_path = Path(download_dir) / rel_path
        if not file_path.exists():
            print(f"[verify_torrent_integrity] Missing file: {file_path}")
            all_ok = False
        elif file_path.stat().st_size != file['length']:
            print(f"[verify_torrent_integrity] Size mismatch: {file_path} (expected {file['length']}, got {file_path.stat().st_size})")
            all_ok = False
    return all_ok

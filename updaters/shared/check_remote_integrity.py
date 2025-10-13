from updaters.shared.robust_get import robust_get
from updaters.shared.parse_hash import parse_hash
from updaters.shared.sha256_hash_check import hash_check

def check_remote_integrity(hash_url, local_file, hash_type, parse_hash_args, parse_hash_kwargs=None, logging_callback=None):
    """
    Fetch hash file from hash_url, parse the correct hash, and check integrity of local_file.
    parse_hash_args: ([match_strings_in_line], hash_position_in_line)
    """
    try:
        resp = robust_get(hash_url, delay=3, retries=10, logging_callback=logging_callback)
        if resp is None or resp.status_code != 200:
            if logging_callback:
                logging_callback(f"[check_remote_integrity] Could not fetch hash file from {hash_url}, resp={resp}")
            return False
        hashes = resp.text
        match_strings_in_line, hash_position_in_line = parse_hash_args
        if parse_hash_kwargs is None:
            parse_hash_kwargs = {}
        hash_val = parse_hash(hashes, match_strings_in_line, hash_position_in_line, logging_callback=logging_callback, **parse_hash_kwargs)
        if not hash_val:
            # Try to log the last non-empty line for debugging
            lines = [line for line in hashes.strip().splitlines() if line.strip()]
            last_line = lines[-1] if lines else ''
            if logging_callback:
                logging_callback(f"[check_remote_integrity] Could not extract hash from {hash_url}. Last non-empty line: '{last_line}'")
            return False
        result = hash_check(local_file, hash_val, hash_type=hash_type, logging_callback=logging_callback)
        if logging_callback:
            if result:
                logging_callback(f"[check_remote_integrity] Integrity OK for {local_file}")
            else:
                logging_callback(f"[check_remote_integrity] Integrity FAIL for {local_file}")
        return result
    except Exception as e:
        if logging_callback:
            logging_callback(f"[check_remote_integrity] Integrity check error: {e}")
        return False

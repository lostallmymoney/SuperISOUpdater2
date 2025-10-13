def parse_hash(hashes: str, match_strings_in_line: list[str], hash_position_in_line: int, logging_callback=None):
    try:
        for line in hashes.strip().splitlines():
            if all(match in line for match in match_strings_in_line):
                hash = line.split()[hash_position_in_line]
                if logging_callback:
                    logging_callback(f"[parse_hash] Online hash: `{hash}`")
                return hash
        if logging_callback:
            logging_callback(f"[parse_hash] No matching line found for match strings {match_strings_in_line} in hashes:\n{hashes}")
        return None
    except Exception as e:
        print(f"[parse_hash DEBUG] Exception: {e}")
        if logging_callback:
            logging_callback(f"[parse_hash] Exception: {e}")
        return None

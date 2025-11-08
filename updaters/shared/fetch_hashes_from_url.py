
from updaters.shared.robust_get import robust_get

def fetch_hashes_from_url(url: str, logging_callback) -> str | None:
    """
    Fetch the contents of a hash/checksum file from a URL and return as string.
    Args:
        url (str): The URL to fetch the hash file from.
    Returns:
        str: The contents of the hash file as a string (for use with parse_hash), or None if the request fails.
    """
    resp = robust_get(url, logging_callback, retries=10, delay=3)
    if resp is None or not hasattr(resp, 'text'):
        logging_callback(f"Failed to fetch hash file from {url}")
        return None
    return resp.text

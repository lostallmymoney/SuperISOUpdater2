import sys
from updaters.shared.robust_get import robust_get

def fetch_expected_file_size(url):
    # Try HEAD request first
    try:
        resp = robust_get(url, method="HEAD", retries=1, delay=2)
        if resp and hasattr(resp, 'headers'):
            size = resp.headers.get('Content-Length')
            content_type = resp.headers.get('Content-Type', '')
            if size is not None and size.isdigit() and int(size) > 1000000 and 'html' not in content_type.lower():
                return int(size)
    except Exception:
        pass

    # Try GET with Range header
    try:
        resp = robust_get(url, method="GET", retries=1, delay=2, headers={"Range": "bytes=0-1048575"})
        if resp and hasattr(resp, 'headers'):
            content_range = resp.headers.get('Content-Range')
            content_type = resp.headers.get('Content-Type', '')
            if content_range:
                total_size = content_range.split('/')[-1]
                if total_size.isdigit() and int(total_size) > 1000000:
                    return int(total_size)
            size = resp.headers.get('Content-Length')
            if size is not None and size.isdigit() and int(size) > 1000000 and 'html' not in content_type.lower():
                return int(size)
    except Exception:
        pass

    # Try normal GET as last resort
    try:
        resp = robust_get(url, method="GET", retries=1, delay=2)
        if resp and hasattr(resp, 'headers'):
            size = resp.headers.get('Content-Length')
            content_type = resp.headers.get('Content-Type', '')
            if size is not None and size.isdigit() and int(size) > 1000000 and 'html' not in content_type.lower():
                return int(size)
    except Exception:
        pass

    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_file_size.py <url1> [<url2> ...]")
        sys.exit(1)
    for url in sys.argv[1:]:
        fetch_expected_file_size(url)

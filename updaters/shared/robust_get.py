
import requests
import time
from tqdm import tqdm
import sys

# --- robust_get: for in-memory requests only ---
def robust_get(url: str, method: str = "GET", retries: int = 5, delay: float = 1.0, logging_callback=None, redirects=True, **kwargs):
    """
    Robust HTTP(S) request with retry, returns a response-like object with .content and .iter_content().
    """
    def report(msg):
        if logging_callback:
            logging_callback(msg)
    # Log the URL being fetched using report()
    report(f"[robust_get] Fetching URL: {url}")
    attempt = 0
    PERMANENT_FAILURE_STATUSES = {400, 401, 410, 422, 451}
    MAX_HTTP_RETRIES = retries if retries != -1 else 10
    MAX_PERMANENT_RETRIES = 5
    while True:
        try:
            kwargs_no_headers = dict(kwargs)
            headers = kwargs_no_headers.pop("headers", {}).copy()
            resp = requests.request(method, url, headers=headers, timeout=5, allow_redirects=redirects, **kwargs_no_headers)
            if resp.status_code in {301, 302, 303, 307, 308}:
                location = resp.headers.get('Location', '(no Location header)')
                report(f"Redirect ({resp.status_code}) for {url} to {location}")
                return None
            elif resp.status_code == 200 or resp.status_code == 206:
                if not resp.encoding:
                    resp.encoding = 'utf-8'
                return resp
            elif resp.status_code in PERMANENT_FAILURE_STATUSES:
                attempt += 1
                report(f"HTTP {resp.status_code} (permanent, attempt {attempt}/{MAX_PERMANENT_RETRIES}): {url}")
                if attempt > MAX_PERMANENT_RETRIES:
                    report(f"Exceeded maximum retries for permanent error {url} (HTTP {resp.status_code})")
                    return None
                else:
                    time.sleep(delay)
                    continue
            else:
                attempt += 1
                report(f"HTTP {resp.status_code} (attempt {attempt}/{MAX_HTTP_RETRIES}): {url}")
                if attempt > MAX_HTTP_RETRIES:
                    report(f"Exceeded maximum retries for {url} (HTTP {resp.status_code})")
                    return None
                else:
                    time.sleep(delay)
                    continue
        except requests.exceptions.RequestException as e:
            report(f"Network error: {e}\nWaiting for connection to resume for {url}...")
            time.sleep(3)
            continue
        except Exception as e:
            report(f"robust_get: Unexpected error: {e}")
            return None

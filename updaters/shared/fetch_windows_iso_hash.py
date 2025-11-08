from updaters.shared.robust_get import robust_get
from bs4 import BeautifulSoup
def fetch_windows_iso_hash(language_label_x64: str, url: str, headers, logging_callback) -> str | None:
    import time
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        resp = robust_get(url, retries=3, delay=1, headers=headers, logging_callback=logging_callback)
        if resp is None or getattr(resp, 'status_code', 200) != 200:
            msg = f"HTTP error or no response (attempt {attempt}/{max_retries})"
            if attempt < max_retries:
                logging_callback(f"[fetch_windows_iso_hash] {msg}, retrying...")
                time.sleep(5)
                continue
            else:
                logging_callback(f"[fetch_windows_iso_hash] {msg}, giving up.")
                return None
        soup = BeautifulSoup(resp.text, "html.parser")
        found_hash = False
        for row in soup.find_all("tr"):
            tds = row.find_all("td")
            if len(tds) == 2 and tds[0].get_text(strip=True) == language_label_x64:
                logging_callback(f"[fetch_windows_iso_hash] Found hash for {language_label_x64}: {tds[1].get_text(strip=True)}")
                return tds[1].get_text(strip=True)
        # No longer parse for Microsoft error messages in the page
        # If not found and no error, treat as retryable unless last attempt
        if attempt < max_retries:
            logging_callback(f"[fetch_windows_iso_hash] Hash not found for {language_label_x64} (attempt {attempt}/{max_retries}), retrying...")
            time.sleep(5)
            continue
        else:
            logging_callback(f"[fetch_windows_iso_hash] Hash not found for {language_label_x64} after {max_retries} attempts, giving up.")
            return None
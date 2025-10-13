from updaters.shared.robust_get import robust_get
from bs4 import BeautifulSoup
def fetch_windows_iso_hash(language_label_x64: str, url: str, headers, logging_callback=None) -> str | None:
    resp = robust_get(url, retries=3, delay=1, headers=headers, logging_callback=logging_callback)
    if resp is None or getattr(resp, 'status_code', 200) != 200:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) == 2 and tds[0].get_text(strip=True) == language_label_x64:
            if logging_callback:
                logging_callback(f"[fetch_windows_iso_hash] Found hash for {language_label_x64}: {tds[1].get_text(strip=True)}")
            return tds[1].get_text(strip=True)
    return None
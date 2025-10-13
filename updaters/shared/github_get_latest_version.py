from functools import cache
from updaters.shared.robust_get import robust_get

@cache
def github_get_latest_version(owner: str, repo: str, log_callback=None) -> dict:
    """Gets the latest version of a software via its GitHub repository"""
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    if log_callback:
        log_callback(f"Fetching latest release from {api_url}")
    resp = robust_get(f"{api_url}/releases/latest", retries=3, delay=1)
    if resp is None:
        if log_callback:
            log_callback(f"Failed to fetch latest release from '{api_url}/releases/latest'")
        raise ConnectionError(f"Failed to fetch latest release from '{api_url}/releases/latest'")
    if getattr(resp, 'status_code', 0) != 200:
        if log_callback:
            log_callback(f"GitHub API error {resp.status_code} for {api_url}/releases/latest: {getattr(resp, 'text', '')}")
        raise ConnectionError(f"GitHub API error {resp.status_code} for {api_url}/releases/latest")
    release = resp.json()
    if log_callback:
        log_callback(f"GitHub release fetched from {api_url}: {release}")
    return release

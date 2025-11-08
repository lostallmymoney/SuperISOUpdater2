from functools import cache
from updaters.shared.robust_get import robust_get

@cache
def github_get_latest_version(owner: str, repo: str, logging_callback) -> dict | None:
    """Gets the latest version of a software via its GitHub repository"""
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    logging_callback(f"Fetching latest release from {api_url}")
    resp = robust_get(f"{api_url}/releases/latest", logging_callback, retries=3, delay=1)
    if resp is None:
        logging_callback(f"Failed to fetch latest release from '{api_url}/releases/latest'")
        return None
    if getattr(resp, 'status_code', 0) != 200:
        logging_callback(f"GitHub API error {resp.status_code} for {api_url}/releases/latest: {getattr(resp, 'text', '')}")
        return None
    release = resp.json()
    tag = release.get('tag_name') or release.get('tag') or 'unknown'
    logging_callback(f"GitHub release fetched from {api_url}: tag={tag}")
    return release

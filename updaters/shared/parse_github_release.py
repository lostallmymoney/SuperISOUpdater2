def parse_github_release(release: dict, logging_callback=None) -> dict:
    """Parses a github release into a shorter, easier to read format"""
    res = {
        "tag": release["tag_name"],
        "files": {},
        "text": release["body"],
        "source_code": release["zipball_url"],
    }
    for asset in release["assets"]:
        res["files"][asset["name"]] = asset["browser_download_url"]
    if logging_callback:
        logging_callback(f"GitHub release parsed: {res}")
    return res

def parse_version_from_soup(soup, tag_path, splitter="H", replace=")") -> list[str] | None:
    """
    Extracts version information from a BeautifulSoup object using a tag path and splitter.
    Args:
        soup: BeautifulSoup object to search in.
        tag_path: List of (tag, kwargs) to traverse, e.g. [("div", {"class": "row"}), ("div", {}), ("p", {"string": lambda t: "Version" in t})]
        splitter: String to split the version string on (default: "H").
        replace: String to remove from the version string (default: ")").
    Returns:
        list[str]: List of version components.
    """
    tag = soup
    for tag_name, kwargs in tag_path:
        tag = tag.find(tag_name, **kwargs)
        if tag is None:
            return None
    text = tag.getText()
    if "Version" not in text:
        return None
    return [
        version_number.strip()
        for version_number in text.split("Version")[1].replace(replace, "").split(splitter)
    ]

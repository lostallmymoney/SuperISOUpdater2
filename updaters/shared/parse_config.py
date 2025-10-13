import tomllib
import logging
from pathlib import Path
from typing import Any

def parse_config(toml_file: Path) -> dict[str, Any] | None:
    """Parse a TOML configuration file and return a dictionary representation."""
    with open(toml_file, "rb") as f:
        toml_dict = tomllib.load(f)
    return parse_config_from_dict(toml_dict)


def parse_config_from_dict(input_dict: dict[str, Any]) -> dict[str, Any]:
    """Recursively parse the nested config dictionary and return a new dictionary where the keys are the directory, unless they are a module's name."""
    new_dict: dict[str, Any] = {}
    for key, value in input_dict.items():
        if isinstance(value, dict):
            if "enabled" in value and not value["enabled"]:
                logging.debug(f"Skipping disabled module {key}")
                del value
                continue
            if "directory" in value:
                logging.debug(f"Found directory {value['directory']}")
                new_key: str = value["directory"]
                del value["directory"]
            else:
                logging.debug(f"Found module {key}")
                new_key = key
            new_dict[new_key] = parse_config_from_dict(value)
        elif key == "enabled":
            continue
        else:
            logging.debug(f"Found key {key}")
            new_dict[key] = value
    return new_dict
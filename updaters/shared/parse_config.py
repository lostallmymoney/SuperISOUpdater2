import json
import tomllib
from pathlib import Path
from typing import Any

def parse_config(toml_file: Path, logging_callback) -> dict[str, Any] | None:
    """Parse a TOML configuration file and return a dictionary representation."""
    with open(toml_file, "rb") as f:
        toml_dict = tomllib.load(f)
    parsed_config = parse_config_from_dict(toml_dict, logging_callback)
    logging_callback(json.dumps(parsed_config, indent=2))
    return parsed_config


def parse_config_from_dict(input_dict: dict[str, Any], logging_callback) -> dict[str, Any]:
    """Recursively parse the nested config dictionary and return a new dictionary where the keys are the directory, unless they are a module's name."""
    new_dict: dict[str, Any] = {}
    for key, value in input_dict.items():
        if isinstance(value, dict):
            if "enabled" in value and not value["enabled"]:
                continue
            if "directory" in value:
                new_key: str = value["directory"]
                child_config = {
                    child_key: child_value
                    for child_key, child_value in value.items()
                    if child_key != "directory"
                }
            else:
                new_key = key
                child_config = value
            new_dict[new_key] = parse_config_from_dict(child_config, logging_callback)
        elif key == "enabled":
            continue
        else:
            new_dict[key] = value
    return new_dict

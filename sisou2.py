import argparse
import concurrent.futures
import logging
import threading
from functools import cache
from pathlib import Path
from typing import Type
from updaters.generic.GenericUpdater import GenericUpdater
from updaters.shared.parse_config import parse_config


_print_lock = threading.Lock()
def logging_callback(msg):
    with _print_lock:
        print(msg, flush=True)

@cache
def get_available_updaters() -> list[Type[GenericUpdater]]:
    """Get a list of available updater classes from the updaters package."""
    import updaters
    updater_classes = []
    for name in getattr(updaters, "__all__", []):
        if name == "GenericUpdater":
            continue
        obj = getattr(updaters, name, None)
        if isinstance(obj, type) and issubclass(obj, GenericUpdater) and obj is not GenericUpdater:
            updater_classes.append(obj)
    return updater_classes

def run_updater(updater: GenericUpdater):
    """Run a single updater (already instantiated)."""
    installer_for = f"{updater.__class__.__name__}{' '+getattr(updater, 'edition', '') if hasattr(updater, 'has_edition') and updater.has_edition() else ''}"
    logging.info(f"[{installer_for}] Checking for updates...")

    def run_local(attempt=1):
        try:
            logging.info(f"[{installer_for}] Downloading and installing the latest version... (attempt {attempt}/5)")
            result = updater.install_latest_version()
            if result:
                logging.info(f"[{installer_for}] Update completed successfully.")
            else:
                if attempt < 5:
                    logging.info(f"[{installer_for}] File CORRUPTED after install. Retrying...")
                    run_local(attempt + 1)
                else:
                    logging.info(f"[{installer_for}] File CORRUPTED after install (integrity still fails). Not retrying further.")
        except Exception:
            logging.exception(f"[{installer_for}] An error occurred while updating. See traceback below.")

    run_local()
    

updaters_list: list[GenericUpdater] = []

def stack_updaters(
    install_path: Path, config: dict, updater_list: list[Type[GenericUpdater]]
):
    global updaters_list
    """Run updaters based on the provided configuration.

    Args:
        install_path (Path): The installation path.
        config (dict): The configuration dictionary.
        updater_list (list[Type[GenericUpdater]]): A list of available updater classes.
    """
    for key, value in config.items():
        # If the key's name is the name of an updater, run said updater using the values as argument, otherwise assume it's a folder's name
        if key in [updater.__name__ for updater in updater_list]:
            updater_class = next(
                updater for updater in updater_list if updater.__name__ == key
            )

            params: list[dict] = [{}]

            editions = value.get("editions", [])
            langs = value.get("langs", [])

            if editions and langs:
                params = [
                    {"edition": edition, "lang": lang}
                    for edition in editions
                    for lang in langs
                ]
            elif editions:
                params = [{"edition": edition} for edition in editions]
            elif langs:
                params = [{"lang": lang} for lang in langs]

            for param in params:
                try:
                    updaters_list.append(updater_class(install_path, logging_callback=logging_callback, **param))
                except Exception:
                    installer_for = f"{key} {param}"
                    logging.exception(
                        f"[{installer_for}] An error occurred while trying to add the installer. See traceback below."
                    )           
        else:
            stack_updaters(install_path / key, value, updater_list)
        
    

        



def main():
    """Main function to run the update process."""
    parser = argparse.ArgumentParser(description="Process a file and set log level")

    # Add the positional argument for the file path
    parser.add_argument("ventoy_path", help="Path to the Ventoy drive")

    # Add the optional argument for log level
    parser.add_argument(
        "-l",
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the log level (default: INFO)",
    )

    # Add the optional argument for config file
    parser.add_argument(
        "-c", "--config-file", help="Path to the config file (default: config.toml)"
    )

    # Add the optional argument for retries
    parser.add_argument(
        "-r",
        "--retries",
        default="0",
        help="Number of retries per file on bad internet connections (use 'all' for infinite retries)",
    )

    args = parser.parse_args()
    # Parse retries
    retries = args.retries
    if isinstance(retries, str) and retries.lower() == "all":
        retries = -1
    else:
        try:
            retries = int(retries)
        except Exception:
            print("Invalid value for --retries/-r. Use an integer or 'all'.")
            exit(1)

    ventoy_path = Path(args.ventoy_path).resolve()

    config_file = Path(args.config_file) if args.config_file else None
    if not config_file:
        logging.info(
            "No config file specified. Trying to find config.toml in the current directory..."
        )
        config_file = Path() / "config.toml"

        if not config_file.is_file():
            logging.info(
                "No config file specified. Trying to find config.toml in the ventoy drive..."
            )
            config_file = ventoy_path / "config.toml"

            if not config_file.is_file():
                logging.info(
                    "No config.toml found in the ventoy drive. Generating one from config.toml.default..."
                )
                with open(
                    Path(__file__).parent / "config.toml.default"
                ) as default_config_file:
                    config_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(config_file, "w") as new_config_file:
                        new_config_file.write(default_config_file.read())
                logging.info(
                    "Generated config.toml in the ventoy drive. Please edit it to your liking and run sisou again."
                )
                return

    config = parse_config(config_file)
    if not config:
        raise ValueError("Configuration file could not be parsed or is empty")

    available_updaters: list[Type[GenericUpdater]] = get_available_updaters()

    stack_updaters(ventoy_path, config, available_updaters)


    global updaters_list
    print(f"Found : {len(updaters_list)} updaters to check")
    # Log all updaters and their edition/lang after stacking
    print("--- Enabled updaters found (class, edition, lang) ---")
    for updater in updaters_list:
        cls_name = updater.__class__.__name__
        edition = getattr(updater, "edition", None)
        lang = getattr(updater, "lang", None)
        print(f"{cls_name} | edition: {edition} | lang: {lang}")
    print("--- End of updaters list ---")

    # After updaters are accumulated, filter them in parallel using 4 threads
    def check_and_filter(updater):
        try:
            result = updater.check_for_updates()
            # Only keep if result is True (needs update) or None (unknown, be safe)
            if result is True or result is None:
                return updater
            return None
        except Exception as e:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        filtered = list(executor.map(check_and_filter, updaters_list))
    # Only keep updaters that returned True or None (need update)
    updaters_list[:] = [u for u in filtered if u is not None]

    print(f"Found : {len(updaters_list)} updaters to update")

    for updater in updaters_list:
        run_updater(updater)

    logging.debug("Finished execution")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user (Ctrl+C). Exiting gracefully.")

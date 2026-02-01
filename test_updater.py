import importlib
import sys
from pathlib import Path


from updaters.shared.parse_config import parse_config


def test_updater(class_name, file_path, edition=None, **kwargs):
    print(f"\n=== Testing {class_name} ===")
    try:
        module_path = f"updaters.{class_name}"
        mod = importlib.import_module(module_path)
        updater_cls = getattr(mod, class_name)
        config = kwargs.pop('config', None)
        updater_kwargs = kwargs.copy()

        def find_nested_config(cfg, key):
            if isinstance(cfg, dict):
                if key in cfg:
                    return cfg[key]
                for v in cfg.values():
                    result = find_nested_config(v, key)
                    if result is not None:
                        return result
            return None

        # If edition is provided, only test that edition
        if edition:
            print(f"\n--- Testing edition: {edition} ---")
            updater_kwargs['edition'] = edition
            updater = updater_cls(Path(file_path), parent_logging_callback=print, **updater_kwargs)
            update_status = updater.check_for_updates()
            print("check_for_updates:", update_status)
            max_attempts = 1
            attempt = 0
            while (update_status is True or update_status is None) and attempt < max_attempts:
                attempt += 1
                print(f"install_latest_version attempt {attempt}:", updater.install_latest_version())
                update_status = updater.check_for_updates()
                print("check_for_updates after install:", update_status)
            if update_status is False:
                print("install_latest_version: SUCCESS (integrity check passed)")
            elif attempt == max_attempts:
                print("install_latest_version: FAILED after 3 attempts (integrity check did not pass)")
            else:
                print("install_latest_version: SKIPPED (integrity check passed, no update needed)")
        else:
            # Use config or fallback logic
            params = find_nested_config(config, class_name) if config else None
            editions_to_test = None
            if isinstance(params, dict):
                if 'editions' in params and isinstance(params['editions'], list) and params['editions']:
                    editions_to_test = params['editions']
            if editions_to_test:
                for ed in editions_to_test:
                    print(f"\n--- Testing edition: {ed} ---")
                    updater_kwargs_edition = updater_kwargs.copy()
                    updater_kwargs_edition['edition'] = ed
                    if isinstance(params, dict) and 'lang' in params:
                        updater_kwargs_edition['lang'] = params['lang']
                    if isinstance(params, dict) and 'langs' in params and not updater_kwargs_edition.get('lang'):
                        langs = params['langs']
                        if isinstance(langs, list) and langs:
                            updater_kwargs_edition['lang'] = langs[0]
                    updater = updater_cls(Path(file_path), parent_logging_callback=print, **updater_kwargs_edition)
                    update_status = updater.check_for_updates()
                    print("check_for_updates:", update_status)
                    max_attempts = 1
                    attempt = 0
                    while (update_status is True or update_status is None) and attempt < max_attempts:
                        attempt += 1
                        print(f"install_latest_version attempt {attempt}:", updater.install_latest_version())
                        update_status = updater.check_for_updates()
                        print("check_for_updates after install:", update_status)
                    if update_status is False:
                        print("install_latest_version: SUCCESS (integrity check passed)")
                    elif attempt == max_attempts:
                        print("install_latest_version: FAILED after 3 attempts (integrity check did not pass)")
                    else:
                        print("install_latest_version: SKIPPED (integrity check passed, no update needed)")
            else:
                # Fallback: single edition or no editions list
                if isinstance(params, dict):
                    if 'edition' in params:
                        updater_kwargs['edition'] = params['edition']
                    if 'lang' in params:
                        updater_kwargs['lang'] = params['lang']
                    if 'langs' in params and not updater_kwargs.get('lang'):
                        langs = params['langs']
                        if isinstance(langs, list) and langs:
                            updater_kwargs['lang'] = langs[0]
                updater = updater_cls(Path(file_path), parent_logging_callback=print, **updater_kwargs)
                update_status = updater.check_for_updates()
                print("check_for_updates:", update_status)
                max_attempts = 1
                attempt = 0
                while (update_status is True or update_status is None) and attempt < max_attempts:
                    attempt += 1
                    print(f"install_latest_version attempt {attempt}:", updater.install_latest_version())
                    update_status = updater.check_for_updates()
                    print("check_for_updates after install:", update_status)
                if update_status is False:
                    print("install_latest_version: SUCCESS (integrity check passed)")
                elif attempt == max_attempts:
                    print("install_latest_version: FAILED after 3 attempts (integrity check did not pass)")
                else:
                    print("install_latest_version: SKIPPED (integrity check passed, no update needed)")
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            print("\n[INFO] Test interrupted by user (Ctrl+C). Exiting cleanly.")
            sys.exit(130)
        print(f"[ERROR] {class_name}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Usage: python3 test_updater.py <class_name> <file_path> [edition]
    try:
        argc = len(sys.argv)
        config_file = Path("config.toml.default")
        config = parse_config(config_file, print)
        if argc == 4:
            # python3 test_updater.py <class_name> <file_path> <edition>
            class_name, file_path, edition = sys.argv[1:4]
            test_updater(class_name, file_path, edition=edition, config=config)
        elif argc == 3:
            # python3 test_updater.py <class_name> <file_path>
            class_name, file_path = sys.argv[1:3]
            test_updater(class_name, file_path, config=config)
        else:
            print("Usage: python3 test_updater.py <class_name> <file_path> [edition]")
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            print("\n[INFO] Test interrupted by user (Ctrl+C). Exiting cleanly.")
            sys.exit(130)
        print(f"[ERROR] {e}")
        sys.exit(1)

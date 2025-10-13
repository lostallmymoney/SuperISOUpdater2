import importlib
import sys
from pathlib import Path


from updaters.shared.parse_config import parse_config


def test_updater(module_path, class_name, file_path, **kwargs):
    print(f"\n=== Testing {class_name} from {module_path} ===")
    try:
        # Import only the requested module directly, not via __init__
        # Always use 'updaters' as the root package
        if not module_path.startswith("updaters."):
            module_path = f"updaters.{module_path}"
        mod = importlib.import_module(module_path)
        updater_cls = getattr(mod, class_name)
        # If config is provided, pass edition/lang if present
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

        params = find_nested_config(config, class_name) if config else None
        editions_to_test = None
        if isinstance(params, dict):
            # Direct dict config (flat)
            if 'editions' in params and isinstance(params['editions'], list) and params['editions']:
                editions_to_test = params['editions']
        if editions_to_test:
            for edition in editions_to_test:
                print(f"\n--- Testing edition: {edition} ---")
                updater_kwargs_edition = updater_kwargs.copy()
                updater_kwargs_edition['edition'] = edition
                if isinstance(params, dict) and 'lang' in params:
                    updater_kwargs_edition['lang'] = params['lang']
                if isinstance(params, dict) and 'langs' in params and not updater_kwargs_edition.get('lang'):
                    langs = params['langs']
                    if isinstance(langs, list) and langs:
                        updater_kwargs_edition['lang'] = langs[0]
                updater = updater_cls(Path(file_path), logging_callback=print, **updater_kwargs_edition)
                update_status = updater.check_for_updates()
                print("check_for_updates:", update_status)
                max_attempts = 1
                attempt = 0
                # Install if update is needed or status is unknown (None)
                while (update_status is True or update_status is None) and attempt < max_attempts:
                    attempt += 1
                    print(f"install_latest_version attempt {attempt}:", updater.install_latest_version())
                    # Re-check integrity after install
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
            updater = updater_cls(Path(file_path), logging_callback=print, **updater_kwargs)
            update_status = updater.check_for_updates()
            print("check_for_updates:", update_status)
            max_attempts = 1
            attempt = 0
            while (update_status is True or update_status is None) and attempt < max_attempts:
                attempt += 1
                print(f"install_latest_version attempt {attempt}:", updater.install_latest_version())
                # Re-check integrity after install
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
    # Always use config.toml.default in the current folder
    # Allow: python3 test_updaters.py HirensBootCDPE /media/cc/Ventoy
    try:
        if len(sys.argv) == 4:
            module_path, class_name, file_path = sys.argv[1:4]
            config_file = Path("config.toml.default")
            config = parse_config(config_file)
            test_updater(module_path, class_name, file_path, config=config)
        elif len(sys.argv) == 3:
            # Accept: python3 test_updaters.py <file_path> <class_name>
            file_path = sys.argv[1]
            class_name = sys.argv[2]
            possible_paths = [
                f"{class_name}",
                f"{class_name}.{class_name}",
                f"shared.{class_name}",
                f"generic.{class_name}",
            ]
            config_file = Path("config.toml.default")
            config = parse_config(config_file)
            for module_path in possible_paths:
                try:
                    test_updater(module_path, class_name, file_path, config=config)
                    break
                except ModuleNotFoundError:
                    continue
            else:
                print(f"Could not find module for class {class_name}. Tried: {[f'updaters.' + p for p in possible_paths]}")
        else:
            print("Usage: python test_updaters.py <module_path> <class_name> <file_path>\n   or: python test_updaters.py <file_path> <class_name>")
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            print("\n[INFO] Test interrupted by user (Ctrl+C). Exiting cleanly.")
            sys.exit(130)
        print(f"[ERROR] {e}")
        sys.exit(1)

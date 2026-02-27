from .read_json import read_json
from .get_default_config import get_default_config

import json
import pathlib
import sys


def get_config(SCRIPT_DIR) -> dict:
    """Load configuration from config.json, creating it if it doesn't exist.

    Args:
        SCRIPT_DIR: Path to the script directory

    Returns:
        dict: Configuration dictionary
    """
    cf = SCRIPT_DIR / "config.json"

    default_config = get_default_config()
    config = {}
    error = ""
    needs_setup = False

    # Required exe paths (must exist)
    required_exes = ["blender_exe", "luminance_cli_exe"]
    # Optional exe paths (can be missing, features will be disabled)
    optional_exes = ["align_image_stack_exe", "rawtherapee_cli_exe"]

    if not cf.exists() or cf.stat().st_size == 0:
        # Config doesn't exist or is empty - create with defaults
        with cf.open("w") as f:
            json.dump(default_config, f, indent=4, sort_keys=True)
        config = default_config.copy()
        config["exe_paths"] = default_config.get("exe_paths", {}).copy()
        needs_setup = True
    else:
        config = read_json(cf)
        # Merge with defaults to ensure all keys exist
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if sub_key not in config[key]:
                        config[key][sub_key] = sub_value

    # Always get exe_paths for later use
    exe_paths = config.get("exe_paths", {})

    # Check if required exe_paths are configured
    for key in required_exes:
        path = exe_paths.get(key, "")
        if not path:
            needs_setup = True
            break

    # If setup is needed, we still return the config - the caller should show the setup dialog
    # This allows the GUI to be created first, then show the dialog

    # Validate required exe_paths (only if not needing setup)
    if not needs_setup:
        for key in required_exes:
            path = exe_paths.get(key, "")
            if not path:
                error = (
                    "You need to configure paths first. Edit the '%s' file and fill in the paths."
                    % cf
                ) + " (%s is empty)" % key
                break
            if not pathlib.Path(path).exists():
                error = (
                    '"%s" in config.json either doesn\'t exist or is an invalid path.'
                    % path
                )

    # Check optional exe_paths and mark as unavailable if missing
    config["_optional_exes_available"] = {}
    config["_needs_setup"] = needs_setup
    for key in optional_exes:
        path = exe_paths.get(key, "")
        if path and pathlib.Path(path).exists():
            config["_optional_exes_available"][key] = True
        else:
            config["_optional_exes_available"][key] = False
            if not needs_setup:  # Only print warning if not in setup mode
                print(
                    "Warning: %s is not available (%s). Related features will be disabled."
                    % (key, path + " not found" if path else "path not configured")
                )

    if error:
        print(error)
        input("Press enter to exit.")
        sys.exit(0)

    return config

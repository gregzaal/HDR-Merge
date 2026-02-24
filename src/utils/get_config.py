
# from src.config import SCRIPT_DIR
from utils.read_json import read_json
from utils.get_default_config import get_default_config

import json
import pathlib
import sys


def get_config(SCRIPT_DIR) -> dict:
    """Load configuration from config.json, creating it if it doesn't exist."""
    cf = SCRIPT_DIR / "config.json"

    default_config = get_default_config()
    config = {}
    error = ""
    missing_json_error = (
        "You need to configure some paths first. Edit the '%s' file and fill in the paths."
        % cf
    )

    # Required exe paths (must exist)
    required_exes = ["blender_exe", "luminance_cli_exe"]
    # Optional exe paths (can be missing, features will be disabled)
    optional_exes = ["align_image_stack_exe", "rawtherapee_cli_exe"]

    if not cf.exists() or cf.stat().st_size == 0:
        with cf.open("w") as f:
            json.dump(default_config, f, indent=4, sort_keys=True)
        error = missing_json_error + " (file does not exist or is empty)"
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

        # Validate required exe_paths
        exe_paths = config.get("exe_paths", {})
        for key in required_exes:
            path = exe_paths.get(key, "")
            if not path:
                error = missing_json_error + " (%s is empty)" % key
                break
            if not pathlib.Path(path).exists():
                error = (
                    '"%s" in config.json either doesn\'t exist or is an invalid path.'
                    % path
                )

        # Check optional exe_paths and mark as unavailable if missing
        config["_optional_exes_available"] = {}
        for key in optional_exes:
            path = exe_paths.get(key, "")
            if path and pathlib.Path(path).exists():
                config["_optional_exes_available"][key] = True
            else:
                config["_optional_exes_available"][key] = False
                print(
                    "Warning: %s is not available (%s). Related features will be disabled."
                    % (key, path + " not found" if path else "path not configured")
                )

    if error:
        print(error)
        input("Press enter to exit.")
        sys.exit(0)

    return config
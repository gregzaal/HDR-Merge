from src.config import SCRIPT_DIR

import json


def save_config(config: dict):
    """Save configuration to config.json."""
    cf = SCRIPT_DIR / "config.json"
    with cf.open("w") as f:
        json.dump(config, f, indent=4, sort_keys=True)
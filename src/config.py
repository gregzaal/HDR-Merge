"""
Global configuration module.

Provides CONFIG and SCRIPT_DIR
"""

import sys
import pathlib

if getattr(sys, "frozen", False):
    SCRIPT_DIR = pathlib.Path(sys.executable).parent  # Built with cx_freeze
else:
    SCRIPT_DIR = pathlib.Path(__file__).resolve().parent.parent

# Import get_config after SCRIPT_DIR is defined to avoid circular imports
from .utils.get_config import get_config

CONFIG = get_config(SCRIPT_DIR)


def reload_config() -> dict:
    """Reload configuration from config.json.
    
    Returns:
        dict: Updated configuration dictionary
    """
    from .utils.get_config import get_config
    return get_config(SCRIPT_DIR)

# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

# Compilation mode, support OS-specific options
# nuitka-project-if: {OS} in ("Windows", "Linux", "Darwin", "FreeBSD"):
#    nuitka-project: --mode=onefile
# nuitka-project-else:
#    nuitka-project: --mode=standalone

# The PySide6 plugin covers qt-plugins
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --include-qt-plugins=qml

import sys

# Initialize configuration FIRST (before any other imports)
import config

config.init()

# Check for CLI mode FIRST (before any other imports to avoid tkinter loading)
if "--cli" in sys.argv:
    from cli import main as cli_main

    cli_main()
    sys.exit(0)

from tkinter import (
    PhotoImage,
    Tk,
)

from center import center
from gui.HDRMergeMaster import HDRMergeMaster
from gui.SetupDialog import SetupDialog
from utils.save_config import save_config

CONFIG = config.CONFIG
SCRIPT_DIR = config.SCRIPT_DIR
EXE_PATHS = CONFIG.get("exe_paths", {})


def main():

    print("This window will report detailed progress of the blender renders.")
    print("Use the other window to start the merging process.")

    global root
    root = Tk()
    root.geometry("450x86")
    center(root)
    png_icon = SCRIPT_DIR / "icons" / "icon.png"
    if png_icon.exists():
        root.iconphoto(True, PhotoImage(file=png_icon.as_posix()))
    else:
        root.iconbitmap(str(SCRIPT_DIR / "icons/icon.ico"))

    # Check if setup is needed (config missing or required paths not configured)
    needs_setup = CONFIG.get("_needs_setup", False)
    if not needs_setup:
        required_keys = ["blender_exe", "luminance_cli_exe"]
        needs_setup = not all(EXE_PATHS.get(key) for key in required_keys)

    if needs_setup:
        # Show setup dialog first
        def on_setup_save(config):
            save_config(config)

        setup_dialog = SetupDialog(root, CONFIG, on_setup_save)
        setup_dialog.wait_window()
        # Reload config after setup
        from config import reload_config

        CONFIG.update(reload_config())

    HDRMergeMaster(root)
    root.mainloop()


if __name__ == "__main__":
    main()

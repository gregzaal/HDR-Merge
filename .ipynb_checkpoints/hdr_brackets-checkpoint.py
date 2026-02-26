from tkinter import (
    PhotoImage,
    Tk,
)

from src.config import SCRIPT_DIR, CONFIG
from src.center import center
from src.gui.HDRMergeMaster import HDRMergeMaster
from src.gui.SetupDialog import SetupDialog
from utils.save_config import save_config

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
        from src.config import reload_config
        CONFIG.update(reload_config())

    HDRMergeMaster(root)
    root.mainloop()

if __name__ == "__main__":
    main()

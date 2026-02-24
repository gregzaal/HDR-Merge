import sys
import pathlib
from tkinter import (
    PhotoImage,
    Tk,
)

from src.config import SCRIPT_DIR, CONFIG
from center import center
from gui.HDRMergeMaster import HDRMergeMaster

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
    HDRMergeMaster(root)
    root.mainloop()

if __name__ == "__main__":
    main()

import sys
import subprocess
import json
import pathlib
import exifread
from pathlib import Path
from math import log
from datetime import datetime
from tkinter import (
    TOP,
    BOTH,
    END,
    HORIZONTAL,
    LEFT,
    RIGHT,
    Y,
    X,
    BooleanVar,
    Button,
    Checkbutton,
    Entry,
    Frame,
    Label,
    PhotoImage,
    Spinbox,
    TclError,
    Tk,
    Listbox,
    SINGLE,
    Scrollbar,
    VERTICAL,
    filedialog,
    messagebox,
    ttk,
    StringVar,
    Toplevel,
)
from concurrent.futures import ThreadPoolExecutor
import threading
from time import sleep

__version__ = "1.2.0"

if getattr(sys, "frozen", False):
    SCRIPT_DIR = pathlib.Path(sys.executable).parent  # Built with cx_freeze
else:
    SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

verbose = False


def center(win):
    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (width // 2)
    # Add 32 to account for titlebar & borders
    y = (win.winfo_screenheight() // 2) - (height + 32 // 2)
    win.geometry("{}x{}+{}+{}".format(width, height, x, y))


def run_subprocess_with_prefix(
    cmd: list, bracket_id: int, label: str, out_folder: pathlib.Path
):
    """Run a subprocess and save output to a timestamped log file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = "bracket_%03d_%s_%s.log" % (bracket_id, label, timestamp)
    log_path = out_folder / "logs" / log_filename
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as log_file:
        result = subprocess.run(cmd, capture_output=True, text=True)
        log_file.write("STDOUT:\n")
        log_file.write(result.stdout)
        log_file.write("\nSTDERR:\n")
        log_file.write(result.stderr)

    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)


def read_json(fp: pathlib.Path) -> dict:
    with fp.open("r") as f:
        s = f.read()
        # Work around invalid JSON when people paste single backslashes in there.
        s = s.replace("\\", "/")
        try:
            return json.loads(s)
        except json.JSONDecodeError as ex:
            raise RuntimeError("Error reading JSON from %s: %s" % (fp, ex))


def get_default_config() -> dict:
    """Get default configuration with OS-specific paths."""
    if sys.platform.startswith("win"):
        # Windows default paths
        default_exe_paths = {
            "align_image_stack_exe": "C:\\Program Files\\Hugin\\bin\\align_image_stack.exe",
            "blender_exe": "C:\\Program Files\\Blender Foundation\\Blender 3.4\\blender.exe",
            "luminance_cli_exe": "C:\\Program Files (x86)\\Luminance HDR\\luminance-hdr-cli.exe",
            "rawtherapee_cli_exe": "C:\\Program Files\\RawTherapee\\5.12\\rawtherapee-cli.exe",
        }
    else:
        # Linux default paths
        default_exe_paths = {
            "align_image_stack_exe": "/usr/bin/align_image_stack",
            "blender_exe": "/usr/bin/blender",
            "luminance_cli_exe": "/usr/bin/luminance-hdr-cli",
            "rawtherapee_cli_exe": "/usr/bin/rawtherapee-cli",
        }

    return {
        "exe_paths": default_exe_paths,
        "gui_settings": {
            "raw_extension": ".dng",
            "tif_extension": ".tif",
            "threads": "6",
            "do_align": False,
            "do_recursive": False,
            "do_raw": False,
            "pp3_file": "",
        },
        "pp3_profiles": [],
    }


def get_config() -> dict:
    """Load configuration from config.json, creating it if it doesn't exist."""
    global SCRIPT_DIR
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


def save_config(config: dict):
    """Save configuration to config.json."""
    global SCRIPT_DIR
    cf = SCRIPT_DIR / "config.json"
    with cf.open("w") as f:
        json.dump(config, f, indent=4, sort_keys=True)


CONFIG = get_config()
EXE_PATHS = CONFIG.get("exe_paths", {})


def play_sound(sf: str):
    if pathlib.Path(sf).exists():
        try:
            from winsound import PlaySound, SND_FILENAME
        except ImportError:
            pass
        else:
            PlaySound(sf, SND_FILENAME)


def notify_phone(msg="Done"):
    message = str(msg)
    icon_dir = SCRIPT_DIR / "icons"
    try:
        notification = __import__("plyer", fromlist=["notification"]).notification
    except ImportError as ex:
        raise RuntimeError(
            "Missing required dependency 'plyer'. Install it with: pip install plyer"
        ) from ex

    notify_kwargs = {
        "title": "HDR Merge Master",
        "message": message,
        "app_name": "HDR Merge Master",
        "timeout": 30,
    }

    if sys.platform.startswith("win"):
        icon_candidates = [icon_dir / "icon.ico", icon_dir / "icon.png"]
    else:
        icon_candidates = [icon_dir / "icon.png", icon_dir / "icon.ico"]

    last_exception = None
    for icon_path in icon_candidates:
        if not icon_path.exists():
            continue
        try:
            notification.notify(**{**notify_kwargs, "app_icon": icon_path.as_posix()})
            return
        except Exception as ex:
            last_exception = ex

    try:
        notification.notify(**notify_kwargs)
    except Exception as ex:
        if last_exception is not None:
            raise RuntimeError("Failed to send system notification") from last_exception
        raise RuntimeError("Failed to send system notification") from ex


def chunks(l, n):
    if n < 1:
        n = 1
    return [l[i : i + n] for i in range(0, len(l), n)]


def get_exif(filepath: pathlib.Path):
    with filepath.open("rb") as f:
        tags = exifread.process_file(f)

    # Try different possible EXIF tag names for image dimensions
    try:
        width = str(tags["Image ImageWidth"])
        height = str(tags["Image ImageLength"])
    except KeyError:
        try:
            width = str(tags["EXIF ExifImageWidth"])
            height = str(tags["EXIF ExifImageLength"])
        except KeyError:
            raise RuntimeError("Could not find image dimensions in EXIF data")

    resolution = width + "x" + height
    shutter_speed = eval(str(tags["EXIF ExposureTime"]))
    try:
        aperture = eval(str(tags["EXIF FNumber"]))
    except ZeroDivisionError:
        aperture = 0
    iso = int(str(tags["EXIF ISOSpeedRatings"]))
    return {
        "resolution": resolution,
        "shutter_speed": shutter_speed,
        "aperture": aperture,
        "iso": iso,
    }


def ev_diff(bright_image, dark_image):
    dr_shutter = log(bright_image["shutter_speed"] / dark_image["shutter_speed"], 2)
    try:
        dr_aperture = log(dark_image["aperture"] / bright_image["aperture"], 1.41421)
    except (ValueError, ZeroDivisionError):
        # No lens data means aperture is 0, and we can't divide by 0 :)
        dr_aperture = 0
    dr_iso = log(bright_image["iso"] / dark_image["iso"], 2)
    return dr_shutter + dr_aperture + dr_iso


class EditProfileDialog(Toplevel):
    """Dialog window for editing a single PP3 profile."""

    def __init__(self, parent, profile, save_callback):
        Toplevel.__init__(self, parent)
        self.title("Edit Profile")
        self.geometry("600x150")
        self.profile = profile
        self.save_callback = save_callback

        self.initUI()
        center(self)
        self.transient(parent)
        self.grab_set()

    def initUI(self):
        padding = 8

        # Profile name
        name_frame = Frame(self)
        name_frame.pack(fill=X, padx=padding, pady=(padding, 4))

        Label(name_frame, text="Profile Name:", width=15, anchor="w").pack(side=LEFT)
        self.profile_name = Entry(name_frame)
        self.profile_name.pack(side=LEFT, fill=X, expand=True)
        self.profile_name.insert(0, self.profile.get("name", ""))
        self.profile_name.bind("<Return>", lambda e: self.save_and_close())

        # Profile path
        path_frame = Frame(self)
        path_frame.pack(fill=X, padx=padding, pady=4)

        Label(path_frame, text="Profile Path:", width=15, anchor="w").pack(side=LEFT)
        self.profile_path = Entry(path_frame)
        self.profile_path.pack(side=LEFT, fill=X, expand=True)
        self.profile_path.insert(0, self.profile.get("path", ""))

        btn_browse = Button(
            path_frame, text="Browse", command=self.browse_profile, width=8
        )
        btn_browse.pack(side=RIGHT, padx=(4, 0))

        # Folder key
        key_frame = Frame(self)
        key_frame.pack(fill=X, padx=padding, pady=4)

        Label(key_frame, text="Folder Key:", width=15, anchor="w").pack(side=LEFT)
        self.folder_key = Entry(key_frame)
        self.folder_key.pack(side=LEFT, fill=X, expand=True)
        self.folder_key.insert(0, self.profile.get("folder_key", ""))
        self.folder_key.bind("<Return>", lambda e: self.save_and_close())

        Label(key_frame, text="(auto-match)", fg="gray").pack(side=LEFT, padx=(4, 0))

        # Button frame
        btn_frame = Frame(self)
        btn_frame.pack(fill=X, padx=padding, pady=(padding, 0))

        btn_save = Button(btn_frame, text="Save", command=self.save_and_close, width=10)
        btn_save.pack(side=RIGHT, padx=(4, 0))

        btn_cancel = Button(btn_frame, text="Cancel", command=self.destroy, width=10)
        btn_cancel.pack(side=RIGHT)

    def browse_profile(self):
        """Browse for profile path."""
        path = filedialog.askopenfilename(
            title="Select PP3 Profile",
            filetypes=[("PP3 files", "*.pp3"), ("All files", "*.*")],
        )
        if path:
            self.profile_path.delete(0, END)
            self.profile_path.insert(0, path)
            # Auto-update name if empty
            if not self.profile_name.get():
                self.profile_name.delete(0, END)
                self.profile_name.insert(0, pathlib.Path(path).stem)

    def save_and_close(self):
        """Save changes and close."""
        self.profile["name"] = self.profile_name.get()
        self.profile["path"] = self.profile_path.get()
        self.profile["folder_key"] = self.folder_key.get()
        self.save_callback()
        self.destroy()


class PP3ProfileManager(Toplevel):
    """Dialog window for managing PP3 profiles."""

    def __init__(self, parent, config, save_callback):
        Toplevel.__init__(self, parent)
        self.parent = parent
        self.title("PP3 Profile Manager")
        self.geometry("600x250")
        self.config = config
        self.save_callback = save_callback
        self.profiles = config.get("pp3_profiles", [])

        self.initUI()
        center(self)
        self.transient(parent)
        self.grab_set()

    def initUI(self):
        padding = 8

        # Profile list section
        list_frame = Frame(self)
        list_frame.pack(fill=BOTH, expand=True, padx=padding, pady=padding)

        # Listbox with scrollbar
        listbox_frame = Frame(list_frame)
        listbox_frame.pack(side=LEFT, fill=BOTH, expand=True)

        self.profile_listbox = Listbox(listbox_frame, height=10, selectmode=SINGLE)
        self.profile_listbox.pack(side=LEFT, fill=BOTH, expand=True)

        scrollbar = Scrollbar(listbox_frame, orient=VERTICAL)
        scrollbar.pack(side=RIGHT, fill=BOTH)
        self.profile_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.profile_listbox.yview)

        self.update_profile_display()

        # Buttons frame
        btn_frame = Frame(list_frame)
        btn_frame.pack(side=RIGHT, padx=(padding, 0))

        btn_add = Button(btn_frame, text="Add", command=self.add_profile, width=10)
        btn_add.pack(side=TOP, pady=(0, 4))

        btn_remove = Button(
            btn_frame, text="Remove", command=self.remove_profile, width=10
        )
        btn_remove.pack(side=TOP, pady=(0, 4))

        btn_clear = Button(
            btn_frame, text="Clear All", command=self.clear_profiles, width=10
        )
        btn_clear.pack(side=TOP, pady=(0, 4))

        btn_set_default = Button(
            btn_frame, text="Set Default", command=self.set_default, width=10
        )
        btn_set_default.pack(side=TOP)

        btn_edit = Button(
            btn_frame, text="Edit Profile", command=self.edit_profile, width=10
        )
        btn_edit.pack(side=TOP, pady=(4, 0))

        # Close button
        btn_close = Button(self, text="Close", command=self.close)
        btn_close.pack(side=RIGHT, padx=padding, pady=(0, padding))

    def update_profile_display(self):
        """Refresh the profile listbox display."""
        self.profile_listbox.delete(0, END)
        for profile in self.profiles:
            default_marker = " [DEFAULT]" if profile.get("default", False) else ""
            key_info = (
                " (%s)" % profile.get("folder_key", "")
                if profile.get("folder_key")
                else ""
            )
            display_name = "%s%s%s" % (
                profile.get("name", "Unnamed"),
                default_marker,
                key_info,
            )
            self.profile_listbox.insert(END, display_name)

    def edit_profile(self):
        """Open edit dialog for selected profile."""
        selection = self.profile_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a profile to edit.")
            return

        index = selection[0]
        profile = self.profiles[index]

        # Open edit dialog with callback to update display and save
        def on_save():
            self.save_profiles()
            self.update_profile_display()

        EditProfileDialog(self, profile, on_save)

    def add_profile(self):
        """Add a new profile."""
        path = filedialog.askopenfilename(
            title="Select PP3 Profile",
            filetypes=[("PP3 files", "*.pp3"), ("All files", "*.*")],
        )
        if not path:
            return

        # Generate name from filename
        name = pathlib.Path(path).stem

        # Check if profile with same path already exists
        for profile in self.profiles:
            if profile.get("path") == path:
                messagebox.showinfo(
                    "Already Exists", "This profile is already in the list."
                )
                return

        new_profile = {
            "name": name,
            "path": path,
            "folder_key": "",
            "default": len(self.profiles) == 0,  # First profile is default
        }
        self.profiles.append(new_profile)
        self.update_profile_display()
        self.save_profiles()

    def remove_profile(self):
        """Remove selected profile."""
        selection = self.profile_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a profile to remove.")
            return

        index = selection[0]
        profile = self.profiles[index]

        if profile.get("default", False):
            if not messagebox.askyesno(
                "Confirm Remove",
                "This is the default profile. Removing it will set another profile as default. Continue?",
            ):
                return

        del self.profiles[index]

        # If we removed the default, set the first remaining as default
        if self.profiles:
            self.profiles[0]["default"] = True

        self.update_profile_display()
        self.save_profiles()

    def clear_profiles(self):
        """Remove all profiles."""
        if not self.profiles:
            return
        if messagebox.askyesno("Clear All", "Remove all PP3 profiles?"):
            self.profiles.clear()
            self.update_profile_display()
            self.save_profiles()

    def set_default(self):
        """Set selected profile as default."""
        selection = self.profile_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a profile to set as default."
            )
            return

        index = selection[0]

        # Clear all defaults
        for profile in self.profiles:
            profile["default"] = False

        # Set selected as default
        self.profiles[index]["default"] = True

        self.update_profile_display()
        self.save_profiles()

    def save_profiles(self):
        """Save profiles to config."""
        self.config["pp3_profiles"] = self.profiles
        self.save_callback(self.config)

    def close(self):
        """Close and refresh folder-profile mappings."""
        self.destroy()
        # Refresh folder-profile mappings in the main window
        if hasattr(self, "parent") and hasattr(self.parent, "refresh_folder_profiles"):
            self.parent.refresh_folder_profiles()


class HDRMergeMaster(Frame):

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master = master
        self.total_sets_global = 0
        self.completed_sets_global = 0
        self.batch_folders = []
        self.folder_profiles = {}  # Maps folder path to profile name
        self._selected_folder = None  # Track currently selected folder

        # Load saved GUI settings
        self.saved_settings = CONFIG.get("gui_settings", {})

        self.initUI()

    def initUI(self):
        self.master.title("HDR Merge Master 2000.1.2.1.rc1")
        self.master.geometry("600x225")
        self.pack(fill=BOTH, expand=True)

        padding = 8
        self.buttons_to_disable = []

        clipboard = ""
        try:
            clipboard = Frame.clipboard_get(self)
        except TclError:
            pass

        # ========== Input ==========
        if clipboard:  # if a path is copied in clipboard, fill it in automatically
            try:
                clippath = pathlib.Path(clipboard)
                if clippath.exists():
                    if clippath.is_dir():
                        self.batch_folders.append(str(clippath).replace("\\", "/"))
            except OSError:
                pass  # Not a valid path.

        # ========== Batch Folders ==========
        r_batch = Frame(master=self)

        lbl_batch = Label(r_batch, width=10, text="Input Folders:")
        lbl_batch.pack(side=LEFT, fill=Y, padx=(padding, 0))

        # Listbox with scrollbar for batch folders
        batch_frame = Frame(r_batch)
        batch_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=padding)

        self.batch_listbox = Listbox(batch_frame, height=4, selectmode=SINGLE)
        self.batch_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        self.batch_listbox.bind("<<ListboxSelect>>", self.on_batch_select)

        batch_scrollbar = Scrollbar(batch_frame, orient=VERTICAL)
        batch_scrollbar.pack(side=RIGHT, fill=BOTH)
        self.batch_listbox.config(yscrollcommand=batch_scrollbar.set)
        batch_scrollbar.config(command=self.batch_listbox.yview)

        self.update_batch_display()

        # Batch buttons (stacked vertically)
        btn_batch_frame = Frame(r_batch)
        btn_batch_frame.pack(
            side=LEFT,
            padx=(
                padding / 2,
                padding,
            ),
        )

        btn_add = Button(
            btn_batch_frame, text="Add", command=self.add_to_batch, width=8
        )
        btn_add.pack(side=TOP, pady=(0, 2))

        btn_remove = Button(
            btn_batch_frame, text="Remove", command=self.remove_from_batch, width=8
        )
        btn_remove.pack(side=TOP, pady=2)

        btn_clear = Button(
            btn_batch_frame, text="Clear All", command=self.clear_batch, width=8
        )
        btn_clear.pack(side=TOP, fill=Y, pady=(2, 0))

        r_batch.pack(fill=BOTH, pady=(padding, 0))

        # ========== Profile Selection ==========
        r_profile = Frame(master=self)

        lbl_profile = Label(r_profile, width=10, text="PP3 Profile:")
        lbl_profile.pack(side=LEFT, fill=Y, padx=(padding, 0))

        # Profile dropdown for selected folder
        profile_frame = Frame(r_profile)
        profile_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=padding)

        self.profile_var = StringVar()
        self.profile_dropdown = ttk.Combobox(
            profile_frame, textvariable=self.profile_var, state="readonly"
        )
        self.profile_dropdown.pack(side=LEFT, fill=X, expand=True)
        self.profile_dropdown.bind("<<ComboboxSelected>>", self.on_profile_change)

        btn_manage_profiles = Button(
            r_profile, text="Manage Profiles...", command=self.open_profile_manager
        )
        btn_manage_profiles.pack(side=RIGHT, padx=(0, padding))

        r_profile.pack(fill=X, pady=(padding, 0))

        # ========== Options =========

        r2 = Frame(master=self)

        lbl_pattern = Label(r2, text="Matching Pattern:")
        lbl_pattern.pack(side=LEFT, padx=(padding, 0))

        # Pattern frame to hold extension and label
        pattern_frame = Frame(r2)
        pattern_frame.pack(side=LEFT, padx=(padding / 2, 0))

        self.extension = Entry(pattern_frame, width=6)
        self.extension.pack(side=TOP, fill=X)
        self.extension.insert(0, self.saved_settings.get("tif_extension", ".tif"))
        self.extension.bind("<Return>", self.save_extension)
        self.buttons_to_disable.append(self.extension)

        self.extension_label = Label(
            pattern_frame, text="(TIFF)", font=("TkDefaultFont", 8)
        )
        self.extension_label.pack(side=TOP)

        lbl_threads = Label(r2, text="Threads:")
        lbl_threads.pack(side=LEFT, padx=(padding, 0))
        self.num_threads = Spinbox(r2, from_=1, to=9999999, width=2)
        self.num_threads.delete(0, "end")
        self.num_threads.insert(0, self.saved_settings.get("threads", "6"))
        self.num_threads.bind("<Return>", self.save_threads)
        self.num_threads.pack(side=LEFT, padx=(padding / 3, 0))
        self.buttons_to_disable.append(self.num_threads)

        self.do_raw = BooleanVar()
        self.do_raw.set(self.saved_settings.get("do_raw", False))
        lbl_raw = Label(r2, text="RAW File:")
        lbl_raw.pack(side=LEFT, padx=(padding, 0))
        self.raw = Checkbutton(
            r2,
            variable=self.do_raw,
            onvalue=True,
            offvalue=False,
            command=self.toggle_raw_extension,
        )
        self.raw.pack(side=LEFT)
        self.buttons_to_disable.append(self.raw)

        # Disable RAW checkbox if RawTherapee CLI is not available
        if not CONFIG.get("_optional_exes_available", {}).get(
            "rawtherapee_cli_exe", False
        ):
            self.raw.config(state="disabled")
            self.do_raw.set(False)

        # Initialize extension field based on saved RAW state
        self.toggle_raw_extension()
        self.do_align = BooleanVar()
        self.do_align.set(self.saved_settings.get("do_align", False))
        lbl_align = Label(r2, text="Align:")
        lbl_align.pack(side=LEFT, padx=(padding, 0))
        self.align = Checkbutton(
            r2, variable=self.do_align, onvalue=True, offvalue=False
        )
        self.align.pack(side=LEFT)
        self.buttons_to_disable.append(self.align)

        # Disable Align checkbox if align_image_stack is not available
        if not CONFIG.get("_optional_exes_available", {}).get(
            "align_image_stack_exe", False
        ):
            self.align.config(state="disabled")
            self.do_align.set(False)

        self.do_recursive = BooleanVar()
        self.do_recursive.set(self.saved_settings.get("do_recursive", False))
        lbl_recursive = Label(r2, text="Recursive:")
        lbl_recursive.pack(side=LEFT, padx=(padding, 0))
        self.recursive = Checkbutton(
            r2, variable=self.do_recursive, onvalue=True, offvalue=False
        )
        self.recursive.pack(side=LEFT)
        self.buttons_to_disable.append(self.recursive)

        self.btn_execute = Button(r2, text="Create HDRs", command=self.execute)
        self.btn_execute.pack(side=RIGHT, fill=X, expand=True, padx=padding)
        self.buttons_to_disable.append(self.btn_execute)

        r2.pack(fill=X, pady=(padding, 0))
        r3 = Frame(master=self)

        self.progress = ttk.Progressbar(
            r3, orient=HORIZONTAL, length=100, mode="determinate"
        )
        self.progress.pack(fill=X, padx=padding, pady=(0, padding))

        r3.pack(fill=X, pady=(padding, 0))

    def set_input_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.input_folder.delete(0, END)
            self.input_folder.insert(0, path)
            self.btn_execute["text"] = "Create HDRs"
            self.btn_execute["command"] = self.execute
            self.progress["value"] = 0

    def set_pp3_file(self):
        """Show file browser and select PP3 profile file."""
        path = filedialog.askopenfilename(
            title="Select PP3 Profile",
            filetypes=[("PP3 files", "*.pp3"), ("All files", "*.*")],
        )
        if path:
            self.pp3_file.delete(0, END)
            self.pp3_file.insert(0, path)

    def toggle_raw_extension(self):
        """Toggle extension field between RAW and TIFF extensions."""
        if self.do_raw.get():
            self.extension.delete(0, END)
            self.extension.insert(0, self.saved_settings.get("raw_extension", ".dng"))
            self.extension_label.config(text="(RAW)")
        else:
            self.extension.delete(0, END)
            self.extension.insert(0, self.saved_settings.get("tif_extension", ".tif"))
            self.extension_label.config(text="(TIFF)")

    def update_batch_display(self):
        """Refresh the batch listbox display."""
        self.batch_listbox.delete(0, END)
        for folder in self.batch_folders:
            self.batch_listbox.insert(END, folder)

    def add_to_batch(self):
        """Show file browser and add selected folder to batch list."""
        path = filedialog.askdirectory()
        if not path:
            return
        if path in self.batch_folders:
            messagebox.showinfo(
                "Already Added", "This folder is already in the batch list."
            )
            return
        self.batch_folders.append(path)
        self.update_batch_display()
        # Auto-assign profile for new folder
        profile = self.get_profile_for_folder(path)
        if profile:
            self.folder_profiles[path] = profile.get("name")

    def remove_from_batch(self):
        """Remove selected folder from batch list."""
        selection = self.batch_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a folder to remove.")
            return
        index = selection[0]
        del self.batch_folders[index]
        self.update_batch_display()

    def clear_batch(self):
        """Remove all folders from batch list."""
        if not self.batch_folders:
            return
        if messagebox.askyesno(
            "Clear Batch", "Remove all folders from the batch list?"
        ):
            self.batch_folders.clear()
            self.update_batch_display()

    def on_batch_select(self, event=None):
        """Update profile dropdown when a folder is selected in the batch list."""
        selection = self.batch_listbox.curselection()
        if not selection:
            self._selected_folder = None
            return
        index = selection[0]
        folder = self.batch_folders[index]
        # self.input_folder.delete(0, END)
        # self.input_folder.insert(0, folder)

        # Store the selected folder for profile dropdown
        self._selected_folder = folder

        # Update profile dropdown for selected folder
        self.update_profile_dropdown(folder)

    def save_extension(self, event=None):
        """Save the current extension to config based on RAW/TIFF mode."""
        extension = self.extension.get()
        if self.do_raw.get():
            CONFIG["gui_settings"]["raw_extension"] = extension
        else:
            CONFIG["gui_settings"]["tif_extension"] = extension
        save_config(CONFIG)

    def save_threads(self, event=None):
        """Save the current thread count to config."""
        CONFIG["gui_settings"]["threads"] = self.num_threads.get()
        save_config(CONFIG)

    def get_profile_for_folder(self, folder_path):
        """Get the PP3 profile for a folder, auto-matching by folder key or using default."""
        profiles = CONFIG.get("pp3_profiles", [])
        if not profiles:
            return None

        folder_name = pathlib.Path(folder_path).name.lower()

        # First check if folder has a manually assigned profile
        if folder_path in self.folder_profiles:
            profile_name = self.folder_profiles[folder_path]
            for profile in profiles:
                if profile.get("name") == profile_name:
                    return profile

        # Then try to auto-match by folder key
        for profile in profiles:
            folder_key = profile.get("folder_key", "").lower()
            if folder_key and folder_key in folder_name:
                return profile

        # Fall back to default profile
        for profile in profiles:
            if profile.get("default", False):
                return profile

        # If no default, return first profile
        return profiles[0] if profiles else None

    def update_profile_dropdown(self, folder_path=None):
        """Update the profile dropdown with available profiles and current selection."""
        profiles = CONFIG.get("pp3_profiles", [])
        profile_names = [p.get("name", "Unnamed") for p in profiles]
        self.profile_dropdown["values"] = profile_names

        if folder_path and folder_path in self.folder_profiles:
            self.profile_var.set(self.folder_profiles[folder_path])
        elif folder_path:
            # Auto-assign profile for new folder
            profile = self.get_profile_for_folder(folder_path)
            if profile:
                self.folder_profiles[folder_path] = profile.get("name")
                self.profile_var.set(profile.get("name"))
            else:
                self.profile_var.set("")
        else:
            self.profile_var.set("")

    def on_profile_change(self, event=None):
        """Update folder-to-profile mapping when dropdown selection changes."""
        # Get the folder from the stored selection, not from listbox
        if not hasattr(self, "_selected_folder") or not self._selected_folder:
            return

        folder = self._selected_folder
        selected_profile = self.profile_var.get()

        if selected_profile:
            self.folder_profiles[folder] = selected_profile
        elif folder in self.folder_profiles:
            del self.folder_profiles[folder]

    def open_profile_manager(self):
        """Open the PP3 Profile Manager dialog."""
        PP3ProfileManager(self, CONFIG, save_config)

    def refresh_folder_profiles(self):
        """Refresh folder-to-profile mappings after profiles are modified."""
        # Clear existing mappings and re-assign based on new profile keys
        old_mappings = dict(self.folder_profiles)
        self.folder_profiles.clear()

        for folder in self.batch_folders:
            profile = self.get_profile_for_folder(folder)
            if profile:
                self.folder_profiles[folder] = profile.get("name")

        # Update the dropdown if a folder is selected
        if self._selected_folder:
            self.update_profile_dropdown(self._selected_folder)

    def process_raw_with_rawtherapee(
        self,
        rawtherapee_cli_exe: str,
        pp3_file: str,
        folder: pathlib.Path,
        extension: str,
    ) -> pathlib.Path:
        """Process RAW files in folder using RawTherapee CLI and output TIFFs to a 'tif' subfolder."""
        print("\nFolder %s: Processing RAW files with RawTherapee..." % folder.name)

        # Determine RAW file extension (default to .dng)
        raw_extension = extension if extension.startswith(".") else "." + extension
        if not raw_extension:
            raw_extension = ".dng"

        # Find all RAW files in the folder
        glob_pattern = "*%s" % raw_extension
        raw_files = list(folder.glob(glob_pattern))

        if not raw_files:
            print(
                "Folder %s: No RAW files found with pattern '%s'"
                % (folder.name, glob_pattern)
            )
            return None

        # Create output folder for TIFFs
        tif_folder = folder / "tif"
        tif_folder.mkdir(parents=True, exist_ok=True)

        # Build RawTherapee CLI command
        # Usage: rawtherapee-cli -c -p profile.pp3 -o output_dir -t -Y input_files
        # -t = TIFF output (16-bit by default)
        # -Y = Overwrite existing files
        # -p = PP3 profile
        # -o = Output directory
        # -c = Process files (must be last before files)
        cmd = [
            rawtherapee_cli_exe,
            "-p",
            pp3_file,  # Apply PP3 profile
            "-o",
            str(tif_folder),  # Output directory
            "-t",  # TIFF output (16-bit uncompressed)
            "-Y",  # Overwrite existing files
            "-c",  # Convert mode (must be last before input files)
        ]

        # Add all RAW files to process
        for raw_file in raw_files:
            cmd.append(str(raw_file))

        print(
            "Folder %s: Running RawTherapee CLI on %d RAW files..."
            % (folder.name, len(raw_files))
        )
        if verbose:
            print("Folder %s: Command: %s" % (folder.name, " ".join(cmd)))

        # Run RawTherapee CLI
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print("Folder %s: RawTherapee CLI error:" % folder.name)
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                raise subprocess.CalledProcessError(result.returncode, cmd)
        except Exception as ex:
            print("Folder %s: Failed to process RAW files: %s" % (folder.name, ex))
            raise

        print(
            "Folder %s: RawTherapee processing complete. TIFFs saved to: %s"
            % (folder.name, tif_folder)
        )
        return tif_folder

    def do_merge(
        self,
        blender_exe: str,
        merge_blend: pathlib.Path,
        merge_py: pathlib.Path,
        exifs,
        out_folder: pathlib.Path,
        filter_used,
        i,
        img_list,
        folder: pathlib.Path,
        luminance_cli_exe,
        align_image_stack_exe,
    ):

        exr_folder = out_folder / "exr"
        jpg_folder = out_folder / "jpg"
        align_folder = out_folder / "aligned"

        exr_folder.mkdir(parents=True, exist_ok=True)
        jpg_folder.mkdir(parents=True, exist_ok=True)

        exr_path = exr_folder / ("merged_%03d.exr" % i)
        jpg_path = jpg_folder / exr_path.with_suffix(".jpg").name

        if exr_path.exists():
            print(
                "Folder %s: Bracket %d: Skipping, %s exists"
                % (folder.name, i, exr_path.relative_to(folder))
            )
            self.completed_sets_global += 1
            print(
                "Completed sets: %d/%d, %.1f%%"
                % (
                    self.completed_sets_global,
                    self.total_sets_global,
                    (self.completed_sets_global / self.total_sets_global) * 100,
                )
            )
            return

        if self.do_align.get():
            if verbose:
                print(
                    "Folder %s: Bracket %d: Aligning images %s"
                    % (folder.name, i, [Path(p.split("___")[0]).name for p in img_list])
                )
            else:
                print("Folder %s: Bracket %d: Aligning images" % (folder.name, i))

            align_folder.mkdir(parents=True, exist_ok=True)
            actual_img_list = [i.split("___")[0] for i in img_list]
            cmd = [
                align_image_stack_exe,
                "-i",
                "-l",
                "-a",
                (align_folder / "align_{}_".format(i)).as_posix(),
                "--gpu",
            ]
            cmd += actual_img_list
            new_img_list = []
            for j, img in enumerate(img_list):
                new_img_list.append(
                    (
                        align_folder
                        / "align_{}_{}.tif___{}".format(
                            i, str(j).zfill(4), img_list[j].split("___")[-1]
                        )
                    ).as_posix()
                )
            run_subprocess_with_prefix(cmd, i, "align", out_folder)
            img_list = new_img_list

        if verbose:
            print(
                "Folder %s: Bracket %d: Merging %s"
                % (folder.name, i, [Path(p.split("___")[0]).name for p in img_list])
            )
        else:
            print("Folder %s: Bracket %d: Merging" % (folder.name, i))

        cmd = [
            blender_exe,
            "--background",
            merge_blend.as_posix(),
            "--factory-startup",
            "--python",
            merge_py.as_posix(),
            "--",
            exifs[0]["resolution"],
            exr_path.as_posix(),
            filter_used,
            str(i),  # Bracket ID
        ]
        cmd += img_list
        run_subprocess_with_prefix(cmd, i, "blender", out_folder)

        # Delete .blend1 backup file created by Blender
        blend1_path = exr_path.with_name("bracket_%03d_sample.blend1" % i)
        if blend1_path.exists():
            blend1_path.unlink()

        cmd = [
            luminance_cli_exe,
            "-l",
            exr_path.as_posix(),
            "-t",
            "reinhard02",
            "-q",
            "98",
            "-o",
            jpg_path.as_posix(),
        ]
        run_subprocess_with_prefix(cmd, i, "luminance", out_folder)
        if verbose:
            print(
                "Folder %s: Bracket %d: Complete %s"
                % (folder.name, i, [Path(p.split("___")[0]).name for p in img_list])
            )
        else:
            print("Folder %s: Bracket %d: Complete" % (folder.name, i))
        self.completed_sets_global += 1
        print(
            "Completed sets: %d/%d, %.1f%%"
            % (
                self.completed_sets_global,
                self.total_sets_global,
                (self.completed_sets_global / self.total_sets_global) * 100,
            )
        )

    def process_folder(
        self,
        folder: pathlib.Path,
        blender_exe: str,
        luminance_cli_exe: str,
        align_image_stack_exe: str,
        merge_blend: pathlib.Path,
        merge_py: pathlib.Path,
        original_extension: str,
        do_align: bool,
        do_raw: bool,
        rawtherapee_cli_exe: str,
        pp3_file: str,
        executor: ThreadPoolExecutor,
    ) -> tuple:
        """Process a single folder and return (num_brackets, num_sets, threads, error)."""
        out_folder = folder / "Merged"

        # If RAW processing is enabled, process RAW files first
        if do_raw and pp3_file and pathlib.Path(pp3_file).exists():
            tif_folder = self.process_raw_with_rawtherapee(
                rawtherapee_cli_exe, pp3_file, folder, original_extension
            )
            if tif_folder:
                # Use the tif folder for subsequent processing
                folder = tif_folder
                # After RAW processing, we look for .tif files
                extension = ".tif"
            else:
                return (0, 0, [], "RAW processing failed")
        else:
            extension = original_extension

        glob = extension
        if "*" not in glob:
            glob = "*%s" % glob
        files = list(folder.glob(glob))

        if not files:
            return (0, 0, [], "No matching files found")

        # Analyze EXIF to determine number of brackets
        exifs = []
        for f in files:
            e = get_exif(f)
            if e in exifs:
                break
            exifs.append(e)
        brackets = len(exifs)
        print("\nFolder: %s" % folder)
        print("Brackets:", brackets)
        sets = chunks(files, brackets)
        print("Sets:", len(sets), "\n")
        # print("Exifs:", json.dumps(exifs, indent=2))
        if verbose:
            print("Exifs:\n", str(exifs).replace("}, {", "},\n{"))
        evs = [
            ev_diff(
                {"shutter_speed": 1000000000, "aperture": 0.1, "iso": 1000000000000}, e
            )
            for e in exifs
        ]
        evs = [ev - min(evs) for ev in evs]

        filter_used = "None"  # self.filter.get().replace(' ', '').replace('+', '_')  # Depreciated

        # Submit merging tasks to the shared executor
        threads = []
        for i, s in enumerate(sets):
            img_list = []
            for ii, img in enumerate(s):
                img_list.append(img.as_posix() + "___" + str(evs[ii]))

            t = executor.submit(
                self.do_merge,
                blender_exe,
                merge_blend,
                merge_py,
                exifs,
                out_folder,
                filter_used,
                i,
                img_list,
                folder,
                luminance_cli_exe,
                align_image_stack_exe,
            )
            threads.append((i, t))

        return (brackets, len(sets), threads, None)

    def execute(self):
        def real_execute():
            folder_start_time = datetime.now()
            folder = None

            global CONFIG
            global EXE_PATHS
            global SCRIPT_DIR
            blender_exe = EXE_PATHS["blender_exe"]
            luminance_cli_exe = EXE_PATHS["luminance_cli_exe"]
            align_image_stack_exe = EXE_PATHS["align_image_stack_exe"]
            rawtherapee_cli_exe = EXE_PATHS["rawtherapee_cli_exe"]
            merge_blend = SCRIPT_DIR / "blender" / "HDR_Merge.blend"
            merge_py = SCRIPT_DIR / "blender" / "blender_merge.py"
            extension = self.extension.get()
            do_align = self.do_align.get()
            do_raw = self.do_raw.get()

            # Save GUI settings to config - update the appropriate extension
            # Update the extension settings based on current RAW state
            if do_raw:
                CONFIG["gui_settings"]["raw_extension"] = extension
                CONFIG["gui_settings"]["tif_extension"] = self.saved_settings.get(
                    "tif_extension", ".tif"
                )
            else:
                CONFIG["gui_settings"]["raw_extension"] = self.saved_settings.get(
                    "raw_extension", ".dng"
                )
                CONFIG["gui_settings"]["tif_extension"] = extension

            CONFIG["gui_settings"]["threads"] = self.num_threads.get()
            CONFIG["gui_settings"]["do_align"] = do_align
            CONFIG["gui_settings"]["do_recursive"] = self.do_recursive.get()
            CONFIG["gui_settings"]["do_raw"] = do_raw

            save_config(CONFIG)

            original_extension = (
                extension  # Keep track of original extension for RAW processing
            )

            # Validate optional features
            optional_exes_available = CONFIG.get("_optional_exes_available", {})

            if do_raw and not optional_exes_available.get("rawtherapee_cli_exe", False):
                messagebox.showerror(
                    "RawTherapee Not Available",
                    "RAW processing is enabled but RawTherapee CLI is not configured or not found!\n\n"
                    "Please configure the RawTherapee CLI path in config.json.",
                )
                for btn in self.buttons_to_disable:
                    btn["state"] = "normal"
                self.btn_execute["text"] = "Create HDRs"
                return

            # Validate RAW processing settings if enabled
            if do_raw:
                # Check if we have any profiles configured
                profiles = CONFIG.get("pp3_profiles", [])
                if not profiles:
                    messagebox.showerror(
                        "PP3 Profile Required",
                        "RAW processing is enabled but no PP3 profiles are configured!\n\n"
                        "Please add at least one PP3 profile using 'Manage Profiles...'.",
                    )
                    for btn in self.buttons_to_disable:
                        btn["state"] = "normal"
                    self.btn_execute["text"] = "Create HDRs"
                    return
                # Change extension to .tif for RAW processing (output from RawTherapee)
                extension = ".tif"

            # Validate Align feature if enabled
            if do_align and not optional_exes_available.get(
                "align_image_stack_exe", False
            ):
                messagebox.showerror(
                    "Align Image Stack Not Available",
                    "Align is enabled but align_image_stack is not configured or not found!\n\n"
                    "Please configure the align_image_stack path in config.json.",
                )
                for btn in self.buttons_to_disable:
                    btn["state"] = "normal"
                self.btn_execute["text"] = "Create HDRs"
                return

            # Determine folders to process
            folders_to_process = []
            do_recursive = self.do_recursive.get()

            if self.batch_folders:
                # Process all folders in batch list
                for batch_folder_path in self.batch_folders:
                    batch_folder = pathlib.Path(batch_folder_path)
                    if not batch_folder.exists():
                        print(
                            "Warning: Batch folder does not exist: %s"
                            % batch_folder_path
                        )
                        continue
                    if do_recursive:
                        # Find all subfolders containing matching files
                        glob = extension
                        if "*" not in glob:
                            glob = "*%s" % glob
                        for f in batch_folder.rglob(glob):
                            parent = f.parent
                            if (
                                parent not in folders_to_process
                                and parent != batch_folder
                            ):
                                folders_to_process.append(parent)
                        print(
                            "Batch folder '%s' (recursive): Found %d subfolders"
                            % (
                                batch_folder_path,
                                len(
                                    [
                                        p
                                        for p in folders_to_process
                                        if str(p).startswith(str(batch_folder))
                                    ]
                                ),
                            )
                        )
                    else:
                        folders_to_process.append(batch_folder)
                print("Batch mode: Processing %d folders" % len(folders_to_process))
                for f in folders_to_process:
                    print("  - %s" % f)
            else:
                folder = pathlib.Path(self.input_folder.get())
                if not folder.exists():
                    messagebox.showerror(
                        "Folder does not exist",
                        "The input path you have selected does not exist!",
                    )
                    return

                # Determine folders to process
                if do_recursive:
                    # Find all subfolders containing matching files
                    glob = extension
                    if "*" not in glob:
                        glob = "*%s" % glob
                    for f in folder.rglob(glob):
                        parent = f.parent
                        if parent not in folders_to_process and parent != folder:
                            folders_to_process.append(parent)
                    print(
                        "Recursive mode: Found %d subfolders" % len(folders_to_process)
                    )
                    print(
                        "Subfolders to process: %s"
                        % [
                            str(subfolder.relative_to(folder))
                            for subfolder in folders_to_process
                        ]
                    )
                else:
                    folders_to_process.append(folder)

            print("Starting [%s]..." % folder_start_time.strftime("%H:%M:%S"))
            self.btn_execute["text"] = "Busy..."
            self.progress["value"] = 0

            for btn in self.buttons_to_disable:
                btn["state"] = "disabled"

            # First pass: calculate total sets across all folders for progress tracking
            total_sets_global = 0
            folder_info = []

            # Determine the file extension to look for in the first pass
            if do_raw:
                # For RAW processing, look for RAW files in the original folders
                raw_extension = self.extension.get()
                if not raw_extension.startswith("."):
                    raw_extension = "." + raw_extension
                if not raw_extension or raw_extension == ".":
                    raw_extension = ".dng"
                first_pass_extension = raw_extension
            else:
                first_pass_extension = extension

            for proc_folder in folders_to_process:
                glob = first_pass_extension
                if "*" not in glob:
                    glob = "*%s" % glob
                files = list(proc_folder.glob(glob))
                if files:
                    exifs = []
                    for f in files:
                        e = get_exif(f)
                        if e in exifs:
                            break
                        exifs.append(e)
                    brackets = len(exifs)
                    if brackets > 0:
                        sets = len(files) // brackets
                        total_sets_global += sets
                        folder_info.append((proc_folder, brackets, sets))

            # Check if any valid folders were found
            if not folder_info:
                print("No matching files found in the input folder.")
                if self.batch_folders:
                    if do_raw:
                        messagebox.showerror(
                            "No matching files",
                            "No RAW files found in any of the batch folders!\n\n"
                            "Please check that the folders contain RAW images with the pattern: '%s'"
                            % first_pass_extension,
                        )
                    else:
                        messagebox.showerror(
                            "No matching files",
                            "No matching files found in any of the batch folders!\n\n"
                            "Please check that the folders contain images with the pattern: '%s'"
                            % extension,
                        )
                else:
                    if do_raw:
                        messagebox.showerror(
                            "No matching files",
                            "No RAW files found in the input folder!\n\n"
                            "Please check that the folder contains RAW images with the pattern: '%s'"
                            % first_pass_extension,
                        )
                    else:
                        messagebox.showerror(
                            "No matching files",
                            "No matching files found in the input folder!\n\n"
                            "Please check that the folder contains images with the pattern: '%s'"
                            % extension,
                        )
                for btn in self.buttons_to_disable:
                    btn["state"] = "normal"
                self.btn_execute["text"] = "Create HDRs"
                return

            self.total_sets_global = total_sets_global
            print("Total sets to process: %d" % total_sets_global)
            self.completed_sets_global = 0

            # Second pass: process all folders concurrently with shared executor
            bracket_list = []
            total_sets = 0
            all_threads = []

            with ThreadPoolExecutor(
                max_workers=int(self.num_threads.get())
            ) as executor:
                # Submit all folder tasks
                for proc_folder, brackets, sets in folder_info:
                    # Get folder-specific PP3 profile
                    profile = self.get_profile_for_folder(str(proc_folder))
                    folder_pp3_file = profile.get("path", "") if profile else ""

                    brackets, sets, threads, error = self.process_folder(
                        proc_folder,
                        blender_exe,
                        luminance_cli_exe,
                        align_image_stack_exe,
                        merge_blend,
                        merge_py,
                        original_extension,
                        do_align,
                        do_raw,
                        rawtherapee_cli_exe,
                        folder_pp3_file,
                        executor,
                    )
                    bracket_list.append(brackets)
                    total_sets += sets
                    all_threads.extend(threads)
                    if error:
                        print("Error processing %s: %s" % (proc_folder, error))

                # Wait for all tasks to complete and update progress
                completed = set()
                while any(not t[1].done() for t in all_threads):
                    sleep(1)
                    self.update()

                    for bracket_idx, tt in all_threads:
                        if not tt.done():
                            continue
                        if bracket_idx in completed:
                            continue
                        try:
                            tt.result()
                        except Exception as ex:
                            print("Bracket %d: Exception - %s" % (bracket_idx, ex))

                        completed.add(bracket_idx)
                        # self.completed_sets_global += 1
                        # print("Completed sets: %d/%d, %.1f%%" % (self.completed_sets_global, self.total_sets_global, (self.completed_sets_global / self.total_sets_global) * 100))

                    # Update global progress
                    progress = (
                        self.completed_sets_global / self.total_sets_global
                    ) * 100
                    self.progress["value"] = int(progress)

            print("Done!!!")
            folder_end_time = datetime.now()
            folder_duration = (folder_end_time - folder_start_time).total_seconds()
            print(
                "Total time: %.1f seconds (%.1f minutes)"
                % (folder_duration, folder_duration / 60)
            )
            print("Alignment: %s" % ("Yes" if do_align else "No"))
            print("Images per bracket: %s" % bracket_list)
            print("Total sets processed: %d" % total_sets)
            print("Threads used: %d" % int(self.num_threads.get()))
            notify_phone(f"Completed {folder}")
            for btn in self.buttons_to_disable:
                btn["state"] = "normal"
            self.btn_execute["text"] = "Done!"
            self.btn_execute["command"] = self.quit
            play_sound("C:/Windows/Media/Speech On.wav")
            self.update()

        # Run in a separate thread to keep UI alive
        threading.Thread(target=real_execute).start()

    def quit(self):
        global root
        root.destroy()


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

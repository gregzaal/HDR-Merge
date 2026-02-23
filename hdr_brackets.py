import sys
import subprocess
import json
import pathlib
import exifread
from pathlib import Path
from math import log
from datetime import datetime
from tkinter import (
    BOTH,
    END,
    HORIZONTAL,
    LEFT,
    RIGHT,
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
)
from tkinter import filedialog, messagebox, ttk
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


def run_subprocess_with_prefix(cmd: list, bracket_id: int, label: str, out_folder: pathlib.Path):
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


def get_exe_paths() -> dict:
    global SCRIPT_DIR
    cf = SCRIPT_DIR / "exe_paths.json"
    default_exe_paths = {"blender_exe": "", "luminance_cli_exe": "", "align_image_stack_exe": ""}
    exe_paths = {}
    error = ""
    missing_json_error = "You need to configure some paths first. Edit the '%s' file and fill in the paths." % cf

    if not cf.exists() or cf.stat().st_size == 0:
        with cf.open("w") as f:
            json.dump(default_exe_paths, f, indent=4, sort_keys=True)
        error = missing_json_error + " (file does not exist or is empty)"
    else:
        exe_paths = read_json(cf)
        for key, path in exe_paths.items():
            if not path:
                error = missing_json_error + " (%s is empty)" % key
                break
            if not pathlib.Path(path).exists():
                error = '"%s" in exe_paths.json either doesn\'t exist or is an invalid path.' % path
    if error:
        print(error)
        input("Press enter to exit.")
        sys.exit(0)
    return exe_paths


EXE_PATHS = get_exe_paths()


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
        raise RuntimeError("Missing required dependency 'plyer'. Install it with: pip install plyer") from ex

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
    return {"resolution": resolution, "shutter_speed": shutter_speed, "aperture": aperture, "iso": iso}


def ev_diff(bright_image, dark_image):
    dr_shutter = log(bright_image["shutter_speed"] / dark_image["shutter_speed"], 2)
    try:
        dr_aperture = log(dark_image["aperture"] / bright_image["aperture"], 1.41421)
    except (ValueError, ZeroDivisionError):
        # No lens data means aperture is 0, and we can't divide by 0 :)
        dr_aperture = 0
    dr_iso = log(bright_image["iso"] / dark_image["iso"], 2)
    return dr_shutter + dr_aperture + dr_iso


class HDRMergeMaster(Frame):

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master = master
        self.total_sets_global = 0
        self.completed_sets_global = 0

        self.initUI()

    def initUI(self):
        self.master.title("HDR Brackets")
        self.master.geometry("600x100")
        self.pack(fill=BOTH, expand=True)

        padding = 8
        self.buttons_to_disable = []

        clipboard = ""
        try:
            clipboard = Frame.clipboard_get(self)
        except TclError:
            pass

        # ========== Input ==========
        r1 = Frame(master=self)
        initial_label = "Select a folder..."
        if clipboard:  # if a path is copied in clipboard, fill it in automatically
            try:
                clippath = pathlib.Path(clipboard)
                if clippath.exists():
                    initial_label = clipboard
            except OSError:
                pass  # Not a valid path.

        lbl_input = Label(r1, text="Input Folder:")
        lbl_input.pack(side=LEFT, padx=(padding, 0))

        self.input_folder = Entry(r1)
        self.input_folder.insert(0, initial_label)
        self.input_folder.pack(side=LEFT, fill=X, expand=True, padx=padding)
        self.buttons_to_disable.append(self.input_folder)

        btn_browse = Button(r1, text="Browse", command=self.set_input_folder)
        btn_browse.pack(side=RIGHT, padx=(0, padding))
        self.buttons_to_disable.append(btn_browse)

        r1.pack(fill=X, pady=(padding, 0))
        r2 = Frame(master=self)

        lbl_pattern = Label(r2, text="Matching Pattern:")
        lbl_pattern.pack(side=LEFT, padx=(padding, 0))
        self.extension = Entry(r2, width=6)
        self.extension.insert(0, ".tif")
        self.extension.pack(side=LEFT, padx=(padding / 2, 0))
        self.buttons_to_disable.append(self.extension)

        lbl_threads = Label(r2, text="Threads:")
        lbl_threads.pack(side=LEFT, padx=(padding, 0))
        self.num_threads = Spinbox(r2, from_=1, to=9999999, width=2)
        self.num_threads.delete(0, "end")
        self.num_threads.insert(0, "6")
        self.num_threads.pack(side=LEFT, padx=(padding / 3, 0))
        self.buttons_to_disable.append(self.num_threads)

        self.do_align = BooleanVar()
        lbl_align = Label(r2, text="Align:")
        lbl_align.pack(side=LEFT, padx=(padding, 0))
        self.align = Checkbutton(r2, variable=self.do_align, onvalue=True, offvalue=False)
        self.align.pack(side=LEFT)
        self.buttons_to_disable.append(self.align)

        self.do_recursive = BooleanVar()
        lbl_recursive = Label(r2, text="Recursive:")
        lbl_recursive.pack(side=LEFT, padx=(padding, 0))
        self.recursive = Checkbutton(
            r2, variable=self.do_recursive, onvalue=True, offvalue=False)
        self.recursive.pack(side=LEFT)
        self.buttons_to_disable.append(self.recursive)

        self.btn_execute = Button(r2, text='Create HDRs', command=self.execute)
        self.btn_execute.pack(side=RIGHT, fill=X, expand=True, padx=padding)
        self.buttons_to_disable.append(self.btn_execute)

        r2.pack(fill=X, pady=(padding, 0))
        r3 = Frame(master=self)

        self.progress = ttk.Progressbar(
            r3, orient=HORIZONTAL, length=100, mode='determinate')
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
            print("Folder %s: Bracket %d: Skipping, %s exists" % (folder.name, i, exr_path.relative_to(folder)))            
            self.completed_sets_global += 1
            print("Completed sets: %d/%d, %.1f%%" % (self.completed_sets_global, self.total_sets_global, (self.completed_sets_global / self.total_sets_global) * 100))
            return

        if self.do_align.get():
            if verbose:
                print("Folder %s: Bracket %d: Aligning images %s" % (folder.name, i, [ Path(p.split("___")[0]).name for p in img_list]))
            else :
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
                        align_folder / "align_{}_{}.tif___{}".format(i, str(j).zfill(4), img_list[j].split("___")[-1])
                    ).as_posix()
                )
            run_subprocess_with_prefix(cmd, i, "align", out_folder)
            img_list = new_img_list

        if verbose:
            print("Folder %s: Bracket %d: Merging %s" % (folder.name, i, [ Path(p.split("___")[0]).name for p in img_list]))
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
            print("Folder %s: Bracket %d: Complete %s" % (folder.name, i, [ Path(p.split("___")[0]).name for p in img_list]))
        else:
            print("Folder %s: Bracket %d: Complete" % (folder.name, i))
        self.completed_sets_global += 1
        print("Completed sets: %d/%d, %.1f%%" % (self.completed_sets_global, self.total_sets_global, (self.completed_sets_global / self.total_sets_global) * 100))

    def process_folder(self, folder: pathlib.Path, blender_exe: str, luminance_cli_exe: str,
                       align_image_stack_exe: str, merge_blend: pathlib.Path, merge_py: pathlib.Path,
                       extension: str, do_align: bool, executor: ThreadPoolExecutor) -> tuple:
        """Process a single folder and return (num_brackets, num_sets, threads, error)."""
        out_folder = folder / "Merged"
        glob = extension
        if '*' not in glob:
            glob = '*%s' % glob
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
        evs = [ev_diff({"shutter_speed": 1000000000, "aperture": 0.1,
                       "iso": 1000000000000}, e) for e in exifs]
        evs = [ev-min(evs) for ev in evs]

        filter_used = "None"  # self.filter.get().replace(' ', '').replace('+', '_')  # Depreciated

        # Submit merging tasks to the shared executor
        threads = []
        for i, s in enumerate(sets):
            img_list = []
            for ii, img in enumerate(s):
                img_list.append(img.as_posix()+'___'+str(evs[ii]))

            t = executor.submit(self.do_merge, blender_exe, merge_blend, merge_py, exifs, out_folder,
                                filter_used, i, img_list, folder, luminance_cli_exe, align_image_stack_exe)
            threads.append((i, t))

        return (brackets, len(sets), threads, None)

    def execute(self):
        def real_execute():
            folder_start_time = datetime.now()
            folder = pathlib.Path(self.input_folder.get())
            if not folder.exists():
                messagebox.showerror("Folder does not exist", "The input path you have selected does not exist!")
                return

            print("Starting [%s]..." % folder_start_time.strftime("%H:%M:%S"))
            self.btn_execute["text"] = "Busy..."
            self.progress["value"] = 0

            for btn in self.buttons_to_disable:
                btn["state"] = "disabled"

            global EXE_PATHS
            global SCRIPT_DIR
            blender_exe = EXE_PATHS["blender_exe"]
            luminance_cli_exe = EXE_PATHS["luminance_cli_exe"]
            align_image_stack_exe = EXE_PATHS["align_image_stack_exe"]
            merge_blend = SCRIPT_DIR / "blender" / "HDR_Merge.blend"
            merge_py = SCRIPT_DIR / "blender" / "blender_merge.py"
            extension = self.extension.get()
            do_align = self.do_align.get()

            # Determine folders to process
            folders_to_process = []
            if self.do_recursive.get():
                # Find all subfolders containing matching files
                glob = extension
                if '*' not in glob:
                    glob = '*%s' % glob
                for f in folder.rglob(glob):
                    parent = f.parent
                    if parent not in folders_to_process and parent != folder:
                        folders_to_process.append(parent)
                print("Recursive mode: Found %d subfolders" % len(folders_to_process))
                print("Subfolders to process: %s" % [str(subfolder.relative_to(folder)) for subfolder in folders_to_process])
            else:
                folders_to_process.append(folder)

            # First pass: calculate total sets across all folders for progress tracking
            total_sets_global = 0
            folder_info = []
            for proc_folder in folders_to_process:
                glob = extension
                if '*' not in glob:
                    glob = '*%s' % glob
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
                messagebox.showerror(
                    "No matching files",
                    "No matching files found in the input folder!\n\n"
                    "Please check that the folder contains images with the pattern: '%s'" % extension
                )
                for btn in self.buttons_to_disable:
                    btn['state'] = 'normal'
                self.btn_execute['text'] = "Create HDRs"
                return

            self.total_sets_global = total_sets_global
            print("Total sets to process: %d" % total_sets_global)
            self.completed_sets_global = 0

            # Second pass: process all folders concurrently with shared executor
            bracket_list = []
            total_sets = 0
            all_threads = []

            with ThreadPoolExecutor(max_workers=int(self.num_threads.get())) as executor:
                # Submit all folder tasks
                for proc_folder, brackets, sets in folder_info:
                    brackets, sets, threads, error = self.process_folder(
                        proc_folder, blender_exe, luminance_cli_exe,
                        align_image_stack_exe, merge_blend, merge_py,
                        extension, do_align, executor)
                    bracket_list.append(brackets)
                    total_sets += sets
                    all_threads.extend(threads)
                    if error:
                        print("Error processing %s: %s" % (proc_folder , error))

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
                            print('Bracket %d: Exception - %s' % (bracket_idx, ex))

                        completed.add(bracket_idx)
                        # self.completed_sets_global += 1
                        # print("Completed sets: %d/%d, %.1f%%" % (self.completed_sets_global, self.total_sets_global, (self.completed_sets_global / self.total_sets_global) * 100))

                    # Update global progress
                    progress = (self.completed_sets_global / self.total_sets_global) * 100
                    self.progress['value'] = int(progress)

            print("Done!!!")
            folder_end_time = datetime.now()
            folder_duration = (folder_end_time - folder_start_time).total_seconds()
            print("Total time: %.1f seconds (%.1f minutes)" % (folder_duration, folder_duration/60))
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

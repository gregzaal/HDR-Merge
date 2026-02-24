"""
HDR Merge Master - GUI Module

Contains the GUI interface for HDR Merge Master application.
All processing logic is delegated to process modules.
"""

import pathlib
import threading
from tkinter import (
    BOTH,
    END,
    HORIZONTAL,
    LEFT,
    RIGHT,
    SINGLE,
    TOP,
    VERTICAL,
    X,
    Y,
    BooleanVar,
    Button,
    Checkbutton,
    Entry,
    Frame,
    Label,
    Listbox,
    Scrollbar,
    Spinbox,
    StringVar,
    TclError,
    filedialog,
    messagebox,
    ttk,
)

from constants import VERSION
from src.config import CONFIG
from utils.save_config import save_config
from gui.PP3ProfileManager import PP3ProfileManager
from process.executor import execute_hdr_processing


class HDRMergeMaster(Frame):
    """Main GUI frame for HDR Merge Master application."""

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master = master
        self.total_sets_global = 0
        self.completed_sets_global = 0
        self.batch_folders = []
        self.folder_profiles = {}  # Maps folder path to profile name
        self._selected_folder = None  # Track currently selected folder
        self._processing_thread = None  # Track processing thread

        # Load saved GUI settings
        self.saved_settings = CONFIG.get("gui_settings", {})

        self.initUI()

    def initUI(self):
        """Initialize the user interface."""
        self.master.title("HDR Merge Master " + VERSION)
        self.master.geometry("600x225")
        self.pack(fill=BOTH, expand=True)

        padding = 8
        self.buttons_to_disable = []

        clipboard = ""
        try:
            clipboard = Frame.clipboard_get(self)
        except TclError:
            pass

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

        # ========== Options ==========
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

        # ========== Progress Bar ==========
        r3 = Frame(master=self)

        self.progress = ttk.Progressbar(
            r3, orient=HORIZONTAL, length=100, mode="determinate"
        )
        self.progress.pack(fill=X, padx=padding, pady=(0, padding))

        r3.pack(fill=X, pady=(padding, 0))

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
        self._selected_folder = folder
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
        old_mappings = dict(self.folder_profiles)
        self.folder_profiles.clear()

        for folder in self.batch_folders:
            profile = self.get_profile_for_folder(folder)
            if profile:
                self.folder_profiles[folder] = profile.get("name")

        # Update the dropdown if a folder is selected
        if self._selected_folder:
            self.update_profile_dropdown(self._selected_folder)

    def _on_progress_update(self, progress_value):
        """Handle progress updates from the executor."""
        self.progress["value"] = progress_value
        self.master.update()

    def _on_processing_complete(self, results):
        """Handle processing completion."""
        for btn in self.buttons_to_disable:
            btn["state"] = "normal"
        self.btn_execute["text"] = "Done!"
        self.btn_execute["command"] = self.quit
        self.master.update()

    def _on_processing_error(self, error_message):
        """Handle processing errors."""
        messagebox.showerror("Processing Error", error_message)
        for btn in self.buttons_to_disable:
            btn["state"] = "normal"
        self.btn_execute["text"] = "Create HDRs"

    def execute(self):
        """Start HDR processing in a background thread."""

        # Validate batch folders
        if not self.batch_folders:
            messagebox.showwarning(
                "No Input Folders", "Please add at least one input folder to process."
            )
            return

        # Validate RAW processing settings if enabled
        if self.do_raw.get():
            profiles = CONFIG.get("pp3_profiles", [])
            if not profiles:
                messagebox.showerror(
                    "PP3 Profile Required",
                    "RAW processing is enabled but no PP3 profiles are configured!\n\n"
                    "Please add at least one PP3 profile using 'Manage Profiles...'.",
                )
                return

        extension = self.extension.get()
        threads = int(self.num_threads.get())
        do_align = self.do_align.get()
        do_raw = self.do_raw.get()
        do_recursive = self.do_recursive.get()

        # Disable buttons during processing
        for btn in self.buttons_to_disable:
            btn["state"] = "disabled"
        self.btn_execute["text"] = "Busy..."
        self.progress["value"] = 0

        # Create and start the processing thread
        self._processing_thread = execute_hdr_processing(
            batch_folders=self.batch_folders,
            folder_profiles=self.folder_profiles,
            extension=extension,
            threads=threads,
            do_align=do_align,
            do_raw=do_raw,
            do_recursive=do_recursive,
            progress_callback=self._on_progress_update,
            completion_callback=self._on_processing_complete,
            log_callback=None,  # Use default print logging
        )
        self._processing_thread.start()

    def quit(self):
        """Quit the application."""
        global root
        root.destroy()

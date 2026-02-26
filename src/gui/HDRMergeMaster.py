# HDR Merge Master - GUI Module

# Contains the GUI interface for HDR Merge Master application.
# All processing logic is delegated to process modules.

import pathlib
import tkinter as tk
from tkinter import (
    BOTH,
    END,
    HORIZONTAL,
    LEFT,
    RIGHT,
    TOP,
    VERTICAL,
    BooleanVar,
    Button,
    Checkbutton,
    Frame,
    Label,
    Scrollbar,
    Spinbox,
    StringVar,
    X,
    Y,
    filedialog,
    messagebox,
    ttk,
)

import json

from constants import VERSION
from process.executor import execute_hdr_processing
from process.folder_analyzer import analyze_folder, find_subfolders
from src.config import CONFIG
from src.gui.PP3ProfileManager import PP3ProfileManager
from src.gui.SetupDialog import SetupDialog
from utils.save_config import save_config


class HDRMergeMaster(Frame):
    # Main GUI frame for HDR Merge Master application.

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master = master
        self.total_sets_global = 0
        self.completed_sets_global = 0
        self.batch_folders = []
        self.folder_profiles = {}  # Maps folder path to profile name
        self.folder_stats = {}  # Maps folder path to analysis dict
        self.folder_align = {}  # Maps folder path to align setting (bool)
        self._selected_folder = None  # Track currently selected folder
        self._processing_thread = None  # Track processing thread
        self._last_clipboard = None  # Track last processed clipboard content

        # Load saved GUI settings
        self.saved_settings = CONFIG.get("gui_settings", {})

        self.initUI()

        # Check clipboard on startup (with a small delay to ensure UI is ready)
        self.master.after(500, self.check_clipboard)
        # Bind focus in to check clipboard
        self.master.bind("<FocusIn>", lambda e: self.check_clipboard())

    def initUI(self):
        # Initialize the user interface.
        self.master.title("HDR Merge Master " + VERSION)
        self.master.geometry("800x400")
        self.pack(fill=BOTH, expand=True)

        padding = 8
        self.buttons_to_disable = []

        # ========== Batch Folders (Treeview Table) - Expandable ==========
        r_batch = Frame(master=self)

        lbl_batch = Label(r_batch, width=12, text="Input Folders:")
        lbl_batch.pack(side=LEFT, fill=Y, padx=(padding, 0))

        # Treeview table with scrollbar - expandable
        table_frame = Frame(r_batch)
        table_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=padding)

        # Create Treeview with columns
        columns = ("folder", "profile", "extension", "raw", "align", "brackets", "sets")
        self.batch_table = ttk.Treeview(
            table_frame,
            columns=columns,
            selectmode="extended",
        )

        # Configure columns
        self.batch_table.column(
            "#0", width=0, stretch=tk.NO, minwidth=0
        )  # Hidden column
        self.batch_table.column("folder", anchor=tk.W, width=200, minwidth=100)
        self.batch_table.column("profile", anchor=tk.W, width=80, minwidth=60)
        self.batch_table.column("extension", anchor=tk.W, width=50, minwidth=40)
        self.batch_table.column("raw", anchor=tk.CENTER, width=40, minwidth=35)
        self.batch_table.column("align", anchor=tk.CENTER, width=45, minwidth=40)
        self.batch_table.column("brackets", anchor=tk.W, width=55, minwidth=40)
        self.batch_table.column("sets", anchor=tk.W, width=40, minwidth=30)

        # Configure headings
        self.batch_table.heading("#0", text="", anchor=tk.W)
        self.batch_table.heading("folder", text="Folder", anchor=tk.W)
        self.batch_table.heading("profile", text="Profile", anchor=tk.W)
        self.batch_table.heading("extension", text="Ext", anchor=tk.W)
        self.batch_table.heading("raw", text="RAW", anchor=tk.CENTER)
        self.batch_table.heading("align", text="Align", anchor=tk.CENTER)
        self.batch_table.heading("brackets", text="Brackets", anchor=tk.W)
        self.batch_table.heading("sets", text="Sets", anchor=tk.W)

        # Add scrollbar
        table_scrollbar = Scrollbar(
            table_frame, orient=VERTICAL, command=self.batch_table.yview
        )
        table_scrollbar.pack(side=RIGHT, fill=BOTH)
        self.batch_table.configure(yscrollcommand=table_scrollbar.set)

        self.batch_table.pack(side=LEFT, fill=BOTH, expand=True)
        self.batch_table.bind("<<TreeviewSelect>>", self.on_batch_select)

        # Batch buttons (stacked vertically)
        btn_batch_frame = Frame(r_batch)
        btn_batch_frame.pack(
            side=LEFT,
            padx=(padding / 2, padding),
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

        # Export/Import buttons
        btn_export = Button(
            btn_batch_frame, text="Export", command=self.export_batch, width=8
        )
        btn_export.pack(side=TOP, pady=(4, 2))

        btn_import = Button(
            btn_batch_frame, text="Import", command=self.import_batch, width=8
        )
        btn_import.pack(side=TOP, pady=2)

        # Recursive checkbox at bottom of button stack
        self.do_recursive_option = BooleanVar()
        self.do_recursive_option.set(self.saved_settings.get("do_recursive", False))
        self.recursive_check = Checkbutton(
            btn_batch_frame,
            variable=self.do_recursive_option,
            onvalue=True,
            offvalue=False,
            text="Recursive",
        )
        self.recursive_check.pack(side=TOP, pady=(4, 0))

        r_batch.pack(fill=BOTH, expand=True, pady=(padding, 0))

        # ========== Profile Selection and Align ==========
        r_profile = Frame(master=self)

        lbl_profile = Label(r_profile, width=12, text="PP3 Profile:")
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

        # Spacer to push button to right
        Frame(r_profile).pack(side=LEFT, fill=X, expand=True)

        # Align checkbox
        self.do_align = BooleanVar()
        self.do_align.set(self.saved_settings.get("do_align", False))

        # Determine alignment method for display
        use_opencv = self.saved_settings.get("use_opencv", False)
        align_text = "Align (OpenCV)" if use_opencv else "Align (Hugin)"

        self.align_check2 = Checkbutton(
            profile_frame,
            variable=self.do_align,
            onvalue=True,
            offvalue=False,
            text=align_text,
            command=self.toggle_folder_align,
        )
        self.align_check2.pack(side=LEFT, padx=(padding, 0))
        self.buttons_to_disable.append(self.align_check2)

        # Check if alignment is available (either OpenCV or Hugin)
        hugin_available = CONFIG.get("_optional_exes_available", {}).get(
            "align_image_stack_exe", False
        )
        align_available = use_opencv or hugin_available

        # Disable Align checkbox if no alignment method is available
        if not align_available:
            self.align_check2.config(state="disabled")
            self.do_align.set(False)

        btn_manage_profiles = Button(
            r_profile, text="Manage Profiles...", command=self.open_profile_manager
        )
        btn_manage_profiles.pack(side=RIGHT, padx=(0, padding))

        r_profile.pack(fill=X, pady=(padding, 0))

        # ========== Options ==========
        r2 = Frame(master=self)

        lbl_threads = Label(r2, text="Threads:")
        lbl_threads.pack(side=LEFT, padx=(50, 0))
        self.num_threads = Spinbox(r2, from_=1, to=9999999, width=6)
        self.num_threads.delete(0, "end")
        self.num_threads.insert(0, self.saved_settings.get("threads", "6"))
        self.num_threads.bind("<Return>", self.save_threads)
        self.num_threads.pack(side=LEFT, padx=(padding, 0))
        self.buttons_to_disable.append(self.num_threads)

        # Cleanup checkbox
        self.do_cleanup = BooleanVar()
        self.do_cleanup.set(self.saved_settings.get("do_cleanup", False))
        self.cleanup_check = Checkbutton(
            r2,
            variable=self.do_cleanup,
            onvalue=True,
            offvalue=False,
            text="Cleanup temporary files",
        )
        self.cleanup_check.pack(side=LEFT, padx=(padding, 0))
        self.buttons_to_disable.append(self.cleanup_check)

        # Spacer to push button to right
        Frame(r2).pack(side=LEFT, fill=X, expand=True)

        btn_setup_dialog = Button(r2, text="Setup", command=self.open_setup_dialog)
        btn_setup_dialog.pack(side=LEFT, padx=(0, padding))

        self.btn_execute = Button(r2, text="Create HDRs", command=self.execute)
        self.btn_execute.pack(side=RIGHT, padx=(0, padding))
        self.buttons_to_disable.append(self.btn_execute)

        r2.pack(fill=X, pady=(padding, 0))

        # ========== Progress Bar ==========
        r4 = Frame(master=self)

        self.progress = ttk.Progressbar(
            r4, orient=HORIZONTAL, length=100, mode="determinate"
        )
        self.progress.pack(fill=X, padx=padding, pady=(padding, padding))

        r4.pack(fill=X)

    def update_batch_display(self):
        """Refresh the batch table display."""
        # Clear all existing items
        for item in self.batch_table.get_children():
            self.batch_table.delete(item)

        # Add folders with their profile info and stats
        for folder in self.batch_folders:
            profile_name = self.folder_profiles.get(folder, "")
            stats = self.folder_stats.get(folder, {})
            brackets = stats.get("brackets", "")
            sets = stats.get("sets", "")
            extension = stats.get("extension", "")
            is_raw = stats.get("is_raw", False)
            raw_text = "Yes" if is_raw else "No"
            align = self.folder_align.get(folder, False)
            align_text = "Yes" if align else "No"
            self.batch_table.insert(
                "",
                END,
                iid=folder,
                values=(
                    folder,
                    profile_name,
                    extension,
                    raw_text,
                    align_text,
                    brackets,
                    sets,
                ),
            )

    def add_to_batch(self):
        """Show file browser and add selected folder(s) to batch list."""
        path = filedialog.askdirectory()
        if not path:
            return
        self.add_path_to_batch(path)

    def add_path_to_batch(self, path):
        """Add a specific folder path to the batch list."""
        if not path:
            return

        # Normalize the input path
        base_path_obj = pathlib.Path(path).absolute()

        # Determine folders to add
        folders_to_add = []

        if self.do_recursive_option.get():
            # Find all subfolders with HDR files
            gui_settings = CONFIG.get("gui_settings", {})
            max_depth = gui_settings.get("recursive_max_depth", 1)
            ignore_folders = gui_settings.get("recursive_ignore_folders", ["Merged"])

            subfolders = find_subfolders(base_path_obj, max_depth, ignore_folders)
            folders_to_add = [str(f.absolute()) for f in subfolders]
        else:
            folders_to_add = [str(base_path_obj)]

        added_any = False
        # Add each folder
        for folder_path in folders_to_add:
            if folder_path in self.batch_folders:
                continue

            # Analyze the folder for brackets and sets (uses config extension lists)
            analysis = analyze_folder(pathlib.Path(folder_path))

            self.batch_folders.append(folder_path)

            # Auto-assign profile for new folder (only if RAW files)
            if analysis.get("is_raw", False):
                # RAW files use profiles
                profile = self.get_profile_for_folder(folder_path)
                if profile:
                    self.folder_profiles[folder_path] = profile.get("name")
            else:
                # Non-RAW (processed) files don't use profiles
                self.folder_profiles[folder_path] = "N/A"

            # Store the folder stats (full analysis dict)
            self.folder_stats[folder_path] = analysis

            # Initialize align setting for new folder
            if folder_path not in self.folder_align:
                self.folder_align[folder_path] = self.do_align.get()

            added_any = True

        if added_any:
            self.update_batch_display()

    def check_clipboard(self):
        """Check clipboard for a valid directory path and add it if found."""
        try:
            clipboard = self.master.clipboard_get()
            if not clipboard or not isinstance(clipboard, str):
                return

            # Clean up: strip whitespace and quotes (often present when "Copy as path" in Windows)
            path_str = clipboard.strip().strip('"')

            if self._last_clipboard == path_str:
                return

            self._last_clipboard = path_str

            path_obj = pathlib.Path(path_str)
            if path_obj.is_dir():
                # If it's a valid directory, add it to batch
                self.add_path_to_batch(str(path_obj.absolute()))
        except Exception:
            # Clipboard might be empty or not contain text
            pass

    def remove_from_batch(self):
        """Remove selected folder from batch list."""
        selection = self.batch_table.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a folder to remove.")
            return

        for item in selection:
            folder = self.batch_table.item(item)["values"][0]
            if folder in self.batch_folders:
                self.batch_folders.remove(folder)
            if folder in self.folder_profiles:
                del self.folder_profiles[folder]
            if folder in self.folder_align:
                del self.folder_align[folder]

        self.update_batch_display()

    def clear_batch(self):
        """Remove all folders from batch list."""
        if not self.batch_folders:
            return
        if messagebox.askyesno(
            "Clear Batch", "Remove all folders from the batch list?"
        ):
            self.batch_folders.clear()
            self.folder_profiles.clear()
            self.folder_align.clear()
            self.update_batch_display()

    def export_batch(self):
        """Export batch list with all options and parameters to a JSON file."""
        if not self.batch_folders:
            messagebox.showwarning("No Batch Data", "No folders in batch list to export.")
            return

        # Build export data with all folder information
        export_data = {
            "version": VERSION,
            "folders": []
        }

        for folder in self.batch_folders:
            stats = self.folder_stats.get(folder, {})
            folder_data = {
                "path": folder,
                "profile": self.folder_profiles.get(folder, ""),
                "align": self.folder_align.get(folder, False),
                "extension": stats.get("extension", ""),
                "is_raw": stats.get("is_raw", False),
                "brackets": stats.get("brackets", 0),
                "sets": stats.get("sets", 0),
            }
            export_data["folders"].append(folder_data)

        # Ask user where to save the JSON file
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Batch List"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            messagebox.showinfo("Export Successful", f"Batch list exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export batch list:\n{str(e)}")

    def import_batch(self):
        """Import batch list with all options and parameters from a JSON file."""
        # Ask user to select a JSON file
        file_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Import Batch List"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)

            if "folders" not in import_data:
                raise ValueError("Invalid batch file format: missing 'folders' key")

            # Ask user if they want to merge or replace
            if self.batch_folders:
                result = messagebox.askyesnocancel(
                    "Import Options",
                    "Batch list already contains folders.\n\n"
                    "Yes - Merge imported folders with existing list\n"
                    "No - Replace existing list with imported folders\n"
                    "Cancel - Abort import"
                )
                if result is None:  # Cancel
                    return
                if result is False:  # Replace
                    self.batch_folders.clear()
                    self.folder_profiles.clear()
                    self.folder_align.clear()
                    self.folder_stats.clear()

            # Import folders
            imported_count = 0
            for folder_data in import_data["folders"]:
                folder_path = folder_data.get("path")
                if not folder_path:
                    continue

                # Skip if already in batch (for merge mode)
                if folder_path in self.batch_folders:
                    continue

                self.batch_folders.append(folder_path)
                self.folder_profiles[folder_path] = folder_data.get("profile", "")
                self.folder_align[folder_path] = folder_data.get("align", False)

                # Restore stats
                self.folder_stats[folder_path] = {
                    "extension": folder_data.get("extension", ""),
                    "is_raw": folder_data.get("is_raw", False),
                    "brackets": folder_data.get("brackets", 0),
                    "sets": folder_data.get("sets", 0),
                }
                imported_count += 1

            self.update_batch_display()
            messagebox.showinfo(
                "Import Successful",
                f"Successfully imported {imported_count} folder(s) from:\n{file_path}"
            )

        except json.JSONDecodeError as e:
            messagebox.showerror("Import Error", f"Invalid JSON file:\n{str(e)}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import batch list:\n{str(e)}")

    def on_batch_select(self, event=None):
        """Update profile dropdown and align checkbox when a folder is selected."""
        selection = self.batch_table.selection()
        if not selection:
            self._selected_folder = None
            return

        # Get the first selected item
        item = selection[0]
        folder = self.batch_table.item(item)["values"][0]
        self._selected_folder = folder

        # Update align checkbox to match folder's setting
        align_setting = self.folder_align.get(folder, False)
        self.do_align.set(align_setting)

        # Check if folder contains RAW files
        stats = self.folder_stats.get(folder, {})
        if not stats.get("is_raw", False):
            # Non-RAW (processed) files don't use profiles - disable dropdown
            self.profile_var.set("N/A")
            self.profile_dropdown.config(state="disabled")
        else:
            # Enable dropdown and update profile
            self.profile_dropdown.config(state="readonly")
            self.update_profile_dropdown(folder)

    def toggle_folder_align(self):
        """Toggle align setting for the currently selected folder."""
        if not hasattr(self, "_selected_folder") or not self._selected_folder:
            # No folder selected, just update the saved setting for future folders
            self.saved_settings["do_align"] = self.do_align.get()
            return

        # Toggle the align setting for the selected folder
        self.folder_align[self._selected_folder] = self.do_align.get()
        self.update_batch_display()

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

        # Check if folder contains RAW files
        stats = self.folder_stats.get(self._selected_folder, {})
        if not stats.get("is_raw", False):
            # Non-RAW (processed) files don't use profiles - ignore changes
            return

        folder = self._selected_folder
        selected_profile = self.profile_var.get()

        if selected_profile:
            self.folder_profiles[folder] = selected_profile
        elif folder in self.folder_profiles:
            del self.folder_profiles[folder]

        # Update the table display to show the new profile
        self.update_batch_display()

    def open_profile_manager(self):
        """Open the PP3 Profile Manager dialog."""
        PP3ProfileManager(self, CONFIG, save_config)

    def open_setup_dialog(self):
        """Open the Setup dialog for configuring executable paths and settings."""

        def on_setup_save(config):
            save_config(config)
            # After saving new config, we should check if any optional executables became available/unavailable
            CONFIG.update(config)
            self.refresh_folder_profiles()  # Refresh profiles in case setup changes affect them
            self.refresh_align_checkbox()  # Refresh align checkbox text if OpenCV setting changed
            self.refresh_cleanup_checkbox()  # Refresh cleanup checkbox state if setting changed

        setup_dialog = SetupDialog(self.master, CONFIG, on_setup_save)
        setup_dialog.grab_set()  # Make the setup dialog modal

    def refresh_cleanup_checkbox(self):
        """Refresh the cleanup checkbox state based on config setting."""
        do_cleanup = CONFIG.get("gui_settings", {}).get("do_cleanup", False)
        self.do_cleanup.set(do_cleanup)

    def refresh_align_checkbox(self):
        """Refresh the align checkbox text based on OpenCV setting."""
        use_opencv = CONFIG.get("gui_settings", {}).get("use_opencv", False)
        align_text = "Align (OpenCV)" if use_opencv else "Align"
        self.align_check2.config(text=align_text)

        # Also update availability check
        hugin_available = CONFIG.get("_optional_exes_available", {}).get(
            "align_image_stack_exe", False
        )
        align_available = use_opencv or hugin_available

        if not align_available:
            self.align_check2.config(state="disabled")
            self.do_align.set(False)
        else:
            self.align_check2.config(state="normal")

    def refresh_folder_profiles(self):
        """Refresh folder-to-profile mappings after profiles are modified."""
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
        self.btn_execute["text"] = "Create HDRs"
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

        # Validate RAW processing settings for folders that need it
        profiles = CONFIG.get("pp3_profiles", [])
        for folder in self.batch_folders:
            stats = self.folder_stats.get(folder, {})
            if stats.get("is_raw", False) and not profiles:
                messagebox.showerror(
                    "PP3 Profile Required",
                    f"RAW processing is required for folder '{folder}' but no PP3 profiles are configured!\n\n"
                    "Please add at least one PP3 profile using 'Manage Profiles...'.",
                )
                return

        threads = int(self.num_threads.get())
        do_recursive = self.do_recursive_option.get()
        do_cleanup = self.do_cleanup.get()

        # Save cleanup setting to config
        CONFIG["gui_settings"]["do_cleanup"] = do_cleanup

        # Build folder_data list from pre-analyzed stats
        folder_data = []
        for folder in self.batch_folders:
            stats = self.folder_stats.get(folder, {})
            folder_data.append(
                {
                    "path": folder,
                    "is_raw": stats.get("is_raw", False),
                    "extension": stats.get("extension", ".tif"),
                    "brackets": stats.get("brackets", 0),
                    "sets": stats.get("sets", 0),
                }
            )

        # Disable buttons during processing
        for btn in self.buttons_to_disable:
            btn["state"] = "disabled"
        self.btn_execute["text"] = "Busy..."
        self.progress["value"] = 0

        # Create and start the processing thread
        self._processing_thread = execute_hdr_processing(
            folder_data=folder_data,
            folder_profiles=self.folder_profiles,
            folder_align=self.folder_align,
            threads=threads,
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

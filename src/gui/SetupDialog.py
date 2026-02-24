"""
Setup Dialog Module

Contains the dialog for configuring executable paths and other settings.
"""

import pathlib
import tkinter as tk
import webbrowser
from tkinter import (
    BOTH,
    END,
    LEFT,
    RIGHT,
    TOP,
    X,
    Button,
    Entry,
    Frame,
    Label,
    Toplevel,
    filedialog,
    messagebox,
    font as tkfont,
    ttk,
)

from src.center import center


class SetupDialog(Toplevel):
    """Dialog window for configuring executable paths and settings."""

    def __init__(self, parent, config, save_callback):
        Toplevel.__init__(self, parent)
        self.parent = parent
        self.title("Setup")
        self.geometry("750x550")
        self.config = config
        self.save_callback = save_callback
        self.exe_paths = dict(config.get("exe_paths", {}))
        
        # Get GUI settings
        gui_settings = config.get("gui_settings", {})
        self.raw_extensions = list(gui_settings.get("raw_extensions", [".dng", ".cr2", ".cr3", ".nef", ".arw"]))
        self.processed_extensions = list(gui_settings.get("processed_extensions", [".tif", ".tiff", ".jpg"]))
        self.recursive_max_depth = gui_settings.get("recursive_max_depth", 1)
        self.recursive_ignore_folders = list(gui_settings.get("recursive_ignore_folders", ["Merged", "tif", "exr", "jpg", "aligned"]))

        # Store entry widgets for later access
        self.entry_widgets = {}

        self.initUI()
        center(self)
        self.transient(parent)
        self.grab_set()

    def initUI(self):
        """Initialize the user interface."""
        padding = 8

        # Create notebook for tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill=BOTH, expand=True, padx=padding, pady=padding)

        # ========== Executable Paths Tab ==========
        exe_frame = Frame(notebook)
        notebook.add(exe_frame, text="Executable Paths")
        self._init_exe_tab(exe_frame, padding)

        # ========== Extensions Tab ==========
        ext_frame = Frame(notebook)
        notebook.add(ext_frame, text="File Extensions")
        self._init_extensions_tab(ext_frame, padding)

        # ========== Recursive Search Tab ==========
        rec_frame = Frame(notebook)
        notebook.add(rec_frame, text="Recursive Search")
        self._init_recursive_tab(rec_frame, padding)

        # Buttons frame (at bottom)
        btn_frame = Frame(self)
        btn_frame.pack(fill=X, padx=padding, pady=(0, padding))

        btn_cancel = Button(btn_frame, text="Cancel", command=self.cancel, width=10)
        btn_cancel.pack(side=RIGHT, padx=(padding, 0))

        btn_save = Button(btn_frame, text="Save", command=self.save, width=10)
        btn_save.pack(side=RIGHT)

    def _init_exe_tab(self, parent, padding):
        """Initialize the Executable Paths tab."""
        # Title label
        title_label = Label(
            parent,
            text="Configure Executable Paths",
            font=("TkDefaultFont", 11, "bold"),
        )
        title_label.pack(anchor="w", pady=(0, padding))

        intro_label = Label(
            parent,
            text="Please configure the paths to the required executable files. "
            "Optional tools can be configured for additional features.",
            wraplength=650,
        )
        intro_label.pack(anchor="w", pady=(0, padding * 2))

        # Executable path fields
        exe_configs = [
            {
                "key": "blender_exe",
                "label": "Blender (Required):",
                "download_url": "https://www.blender.org/download/",
            },
            {
                "key": "luminance_cli_exe",
                "label": "Luminance HDR CLI (Required):",
                "download_url": "https://sourceforge.net/projects/qtpfsgui/files/luminance/",
            },
            {
                "key": "align_image_stack_exe",
                "label": "Align Image Stack (Optional - Hugin):",
                "download_url": "https://hugin.sourceforge.io/download/",
            },
            {
                "key": "rawtherapee_cli_exe",
                "label": "RawTherapee CLI (Optional):",
                "download_url": "https://rawtherapee.com/downloads/",
            },
        ]

        for exe_config in exe_configs:
            self._create_exe_field(
                parent,
                exe_config["key"],
                exe_config["label"],
                exe_config["download_url"],
            )

    def _init_extensions_tab(self, parent, padding):
        """Initialize the File Extensions tab."""
        # RAW Extensions section
        raw_frame = Frame(parent)
        raw_frame.pack(fill=X, pady=(padding, padding * 2))

        Label(
            raw_frame,
            text="RAW File Extensions:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        Label(
            raw_frame,
            text="Enter comma-separated list of RAW file extensions:",
            fg="gray",
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", pady=(0, 4))

        self.raw_ext_entry = Entry(raw_frame, width=60)
        self.raw_ext_entry.pack(fill=X)
        self.raw_ext_entry.insert(0, ", ".join(self.raw_extensions))

        # Processed Extensions section
        proc_frame = Frame(parent)
        proc_frame.pack(fill=X, pady=padding)

        Label(
            proc_frame,
            text="Processed File Extensions:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        Label(
            proc_frame,
            text="Enter comma-separated list of processed/output file extensions:",
            fg="gray",
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", pady=(0, 4))

        self.proc_ext_entry = Entry(proc_frame, width=60)
        self.proc_ext_entry.pack(fill=X)
        self.proc_ext_entry.insert(0, ", ".join(self.processed_extensions))

    def _init_recursive_tab(self, parent, padding):
        """Initialize the Recursive Search tab."""
        # Max depth section
        depth_frame = Frame(parent)
        depth_frame.pack(fill=X, pady=(padding, padding * 2))

        Label(
            depth_frame,
            text="Maximum Search Depth:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        depth_entry_frame = Frame(depth_frame)
        depth_entry_frame.pack(fill=X)

        self.depth_entry = Entry(depth_entry_frame, width=10)
        self.depth_entry.pack(side=LEFT)
        self.depth_entry.insert(0, str(self.recursive_max_depth))

        Label(
            depth_entry_frame,
            text="  (1 = immediate subfolders only, 2 = one level deeper, etc.)",
            fg="gray",
            font=("TkDefaultFont", 8),
        ).pack(side=LEFT, padx=(8, 0))

        # Ignore folders section
        ignore_frame = Frame(parent)
        ignore_frame.pack(fill=X, pady=padding)

        Label(
            ignore_frame,
            text="Folders to Ignore:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        Label(
            ignore_frame,
            text="Enter comma-separated list of folder names to skip during recursive search:",
            fg="gray",
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", pady=(0, 4))

        self.ignore_entry = Entry(ignore_frame, width=60)
        self.ignore_entry.pack(fill=X)
        self.ignore_entry.insert(0, ", ".join(self.recursive_ignore_folders))

        Label(
            ignore_frame,
            text="Default: Merged, tif, exr, jpg, aligned",
            fg="gray",
            font=("TkDefaultFont", 8),
        ).pack(anchor="w", pady=(4, 0))

    def _create_exe_field(self, parent, key, label_text, download_url):
        """Create a labeled entry field with browse button and download link."""
        frame = Frame(parent)
        frame.pack(fill=X, pady=4)

        # Label
        label = Label(frame, text=label_text, width=35, anchor="w")
        label.pack(side=LEFT)

        # Entry field
        entry = Entry(frame, width=50)
        entry.insert(0, self.exe_paths.get(key, ""))
        entry.pack(side=LEFT, fill=X, expand=True, padx=8)
        self.entry_widgets[key] = entry

        # Browse button
        btn_browse = Button(frame, text="Browse...", command=lambda: self.browse(key))
        btn_browse.pack(side=LEFT, padx=(0, 8))

        # Download link (below the field)
        link_frame = Frame(parent)
        link_frame.pack(fill=X, pady=(0, 8), padx=(140, 0))

        link_label = Label(
            link_frame,
            text="Download: ",
            fg="gray",
            font=("TkDefaultFont", 8),
        )
        link_label.pack(side=LEFT)

        link = Label(
            link_frame,
            text=download_url.replace("https://", ""),
            fg="blue",
            cursor="hand2",
            font=("TkDefaultFont", 8, "underline"),
        )
        link.pack(side=LEFT)

        # Make the link open the URL when clicked
        link.bind("<Button-1>", lambda e: self._open_url(download_url))
        # Add hover effect
        link.bind("<Enter>", lambda e: link.config(fg="darkblue"))
        link.bind("<Leave>", lambda e: link.config(fg="blue"))

    def browse(self, key):
        """Open file dialog to browse for executable."""
        current_path = self.entry_widgets[key].get()
        initial_dir = str(pathlib.Path(current_path).parent) if current_path else None

        file_path = filedialog.askopenfilename(
            title=f"Select {key.replace('_', ' ').title()}",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")],
            initialdir=initial_dir,
        )

        if file_path:
            self.entry_widgets[key].delete(0, END)
            self.entry_widgets[key].insert(0, file_path)

    def _open_url(self, url):
        """Open URL in default browser."""
        webbrowser.open(url)

    def save(self):
        """Save the configured paths and settings and close dialog."""
        # Collect executable paths
        new_exe_paths = {}
        for key, entry in self.entry_widgets.items():
            new_exe_paths[key] = entry.get().strip()

        # Validate required paths
        required_keys = ["blender_exe", "luminance_cli_exe"]
        missing_required = []
        for key in required_keys:
            if not new_exe_paths.get(key):
                missing_required.append(key.replace("_exe", "").replace("_", " ").title())

        if missing_required:
            messagebox.showerror(
                "Missing Required Paths",
                f"The following required executable paths are not set:\n\n"
                + "\n".join(f"  - {name}" for name in missing_required)
                + "\n\nPlease configure all required paths before saving.",
            )
            return

        # Validate that required files exist
        missing_files = []
        for key in required_keys:
            path = new_exe_paths.get(key, "")
            if path and not pathlib.Path(path).exists():
                missing_files.append(f"{key.replace('_exe', '').replace('_', ' ').title()}: {path}")

        if missing_files:
            result = messagebox.askyesno(
                "Files Not Found",
                "The following required executable files were not found:\n\n"
                + "\n".join(f"  - {path}" for path in missing_files)
                + "\n\nDo you want to save anyway? (The application may not work correctly)",
            )
            if not result:
                return

        # Parse extension lists
        try:
            raw_extensions = [
                ext.strip().lower() if ext.strip().startswith(".") else "." + ext.strip().lower()
                for ext in self.raw_ext_entry.get().split(",")
                if ext.strip()
            ]
            processed_extensions = [
                ext.strip().lower() if ext.strip().startswith(".") else "." + ext.strip().lower()
                for ext in self.proc_ext_entry.get().split(",")
                if ext.strip()
            ]
        except Exception as e:
            messagebox.showerror("Invalid Extensions", f"Error parsing extensions: {e}")
            return

        if not raw_extensions:
            messagebox.showerror("Invalid Extensions", "Please enter at least one RAW file extension.")
            return

        if not processed_extensions:
            messagebox.showerror("Invalid Extensions", "Please enter at least one processed file extension.")
            return

        # Parse recursive settings
        try:
            max_depth = int(self.depth_entry.get())
            if max_depth < 1:
                raise ValueError("Depth must be at least 1")
        except ValueError:
            messagebox.showerror("Invalid Depth", "Please enter a valid number (1 or greater) for max depth.")
            return

        ignore_folders = [
            f.strip() for f in self.ignore_entry.get().split(",") if f.strip()
        ]

        # Update config
        self.config["exe_paths"] = new_exe_paths
        self.config["gui_settings"]["raw_extensions"] = raw_extensions
        self.config["gui_settings"]["processed_extensions"] = processed_extensions
        self.config["gui_settings"]["recursive_max_depth"] = max_depth
        self.config["gui_settings"]["recursive_ignore_folders"] = ignore_folders
        
        self.save_callback(self.config)

        messagebox.showinfo(
            "Setup Complete",
            "Settings have been saved successfully!\n\n"
            "You can now start using HDR Merge Master.",
        )
        self.destroy()

    def cancel(self):
        """Close dialog without saving."""
        # Check if any required paths are missing
        required_keys = ["blender_exe", "luminance_cli_exe"]
        has_required = any(self.config.get("exe_paths", {}).get(key) for key in required_keys)

        if not has_required:
            messagebox.showerror(
                "Setup Required",
                "You must configure the executable paths before using HDR Merge Master.",
            )
            return

        self.destroy()

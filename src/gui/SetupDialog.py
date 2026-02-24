"""
Setup Dialog Module

Contains the dialog for configuring executable paths.
"""

import pathlib
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
)

from src.center import center


class SetupDialog(Toplevel):
    """Dialog window for configuring executable paths."""

    def __init__(self, parent, config, save_callback):
        Toplevel.__init__(self, parent)
        self.parent = parent
        self.title("Setup - Executable Paths")
        self.geometry("700x400")
        self.config = config
        self.save_callback = save_callback
        self.exe_paths = dict(config.get("exe_paths", {}))

        # Store entry widgets for later access
        self.entry_widgets = {}

        self.initUI()
        center(self)
        self.transient(parent)
        self.grab_set()

    def initUI(self):
        """Initialize the user interface."""
        padding = 8

        # Main container
        main_frame = Frame(self)
        main_frame.pack(fill=BOTH, expand=True, padx=padding, pady=padding)

        # Title label
        title_label = Label(
            main_frame,
            text="Configure Executable Paths",
            font=("TkDefaultFont", 11, "bold"),
        )
        title_label.pack(anchor="w", pady=(0, padding))

        intro_label = Label(
            main_frame,
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
                "download_url": "https://www.blender.org/download/releases/4-5/",
            },
            {
                "key": "luminance_cli_exe",
                "label": "Luminance HDR CLI (Required):",
                "download_url": "https://sourceforge.net/projects/qtpfsgui/files/luminance/",
            },
            {
                "key": "align_image_stack_exe",
                "label": "Align Image Stack (Optional):",
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
                main_frame,
                exe_config["key"],
                exe_config["label"],
                exe_config["download_url"],
            )

        # Buttons frame
        btn_frame = Frame(main_frame)
        btn_frame.pack(side=RIGHT, pady=(padding * 2, 0))

        btn_cancel = Button(btn_frame, text="Cancel", command=self.cancel, width=10)
        btn_cancel.pack(side=RIGHT, padx=(padding, 0))

        btn_save = Button(btn_frame, text="Save", command=self.save, width=10)
        btn_save.pack(side=RIGHT)

    def _create_exe_field(self, parent, key, label_text, download_url):
        """Create a labeled entry field with browse button and download link."""
        frame = Frame(parent)
        frame.pack(fill=X, pady=4)

        # Label
        label = Label(frame, text=label_text, width=25, anchor="w")
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
        link_frame.pack(fill=X, pady=(0, 8), padx=(0, 0))

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
        import webbrowser

        webbrowser.open(url)

    def save(self):
        """Save the configured paths and close dialog."""
        # Collect all paths from entry widgets
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

        # Validate that files exist
        missing_files = []
        for key, path in new_exe_paths.items():
            if path and not pathlib.Path(path).exists():
                missing_files.append(f"{key.replace('_exe', '').replace('_', ' ').title()}: {path}")

        if missing_files:
            result = messagebox.askyesno(
                "Files Not Found",
                "The following executable files were not found:\n\n"
                + "\n".join(f"  - {path}" for path in missing_files)
                + "\n\nDo you want to save anyway? (Features using missing executables will be disabled)",
            )
            if not result:
                return

        # Update config
        self.config["exe_paths"] = new_exe_paths
        self.save_callback(self.config)

        messagebox.showinfo(
            "Setup Complete",
            "Executable paths have been saved successfully!\n\n"
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

from src.center import center
import pathlib
from tkinter import END, LEFT, RIGHT, X, Button, Entry, Frame, Label, Toplevel, filedialog


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
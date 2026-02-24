from src.center import center
from src.gui.EditProfileDialog import EditProfileDialog



import pathlib
from tkinter import BOTH, END, LEFT, RIGHT, SINGLE, TOP, VERTICAL, Button, Frame, Listbox, Scrollbar, Toplevel, filedialog, messagebox


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
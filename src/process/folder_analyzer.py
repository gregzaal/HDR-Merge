"""
Folder Analyzer Module

Contains utilities for analyzing HDR folders to determine bracket counts and sets.
Automatically uses extension lists from config.
"""

import pathlib
from src.config import CONFIG
from utils.get_exif import get_exif


def analyze_folder(folder_path: pathlib.Path) -> dict:
    """
    Analyze a folder to determine the number of brackets and sets.
    
    Uses extension lists from config to detect both RAW and processed files.
    
    Args:
        folder_path: Path to the folder to analyze
    
    Returns:
        dict: Dictionary containing:
            - brackets: Number of unique exposure brackets
            - sets: Number of complete HDR sets
            - is_raw: Boolean indicating if files are RAW or processed
            - extension: The primary extension found
    """
    folder = pathlib.Path(folder_path)
    if not folder.exists():
        return {"brackets": 0, "sets": 0, "is_raw": False, "extension": ""}
    
    # Get extension lists from config
    gui_settings = CONFIG.get("gui_settings", {})
    raw_extensions = gui_settings.get("raw_extensions", [])
    processed_extensions = gui_settings.get("processed_extensions", [])
    
    # Find all matching files (both RAW and processed)
    all_extensions = raw_extensions + processed_extensions
    files = []
    for ext in all_extensions:
        files.extend(folder.glob(f"*{ext}"))
        files.extend(folder.glob(f"*{ext.upper()}"))  # Also check uppercase extensions
    
    if not files:
        return {"brackets": 0, "sets": 0, "is_raw": False, "extension": ""}
    
    # Determine if files are RAW or processed by checking the first file
    first_file = files[0]
    file_ext = first_file.suffix.lower()
    is_raw = file_ext in raw_extensions
    
    # Analyze EXIF to determine number of unique brackets
    exifs = []
    for f in files:
        e = get_exif(f)
        if e in exifs:
            break
        exifs.append(e)
    
    brackets = len(exifs)
    
    if brackets == 0:
        return {"brackets": 0, "sets": 0, "is_raw": is_raw, "extension": file_ext}
    
    # Calculate number of complete sets
    sets = len(files) // brackets
    
    return {
        "brackets": brackets,
        "sets": sets,
        "is_raw": is_raw,
        "extension": file_ext,
    }


def find_subfolders(folder_path: pathlib.Path, max_depth: int = 1, ignore_folders: list = None) -> list:
    """
    Find all subfolders containing HDR image files.
    
    Args:
        folder_path: Root folder to search
        max_depth: Maximum depth to search (default: 1 = immediate subfolders only)
        ignore_folders: List of folder names to ignore (default: from config)
    
    Returns:
        list: List of pathlib.Path objects for folders containing HDR files
    """
    if ignore_folders is None:
        gui_settings = CONFIG.get("gui_settings", {})
        ignore_folders = gui_settings.get("recursive_ignore_folders", ["Merged"])
    
    # Get extension lists from config
    gui_settings = CONFIG.get("gui_settings", {})
    raw_extensions = gui_settings.get("raw_extensions", [])
    processed_extensions = gui_settings.get("processed_extensions", [])
    all_extensions = raw_extensions + processed_extensions
    
    found_folders = []
    
    def has_hdr_files(folder: pathlib.Path) -> bool:
        """Check if folder contains HDR image files."""
        for ext in all_extensions:
            if list(folder.glob(f"*{ext}")) or list(folder.glob(f"*{ext.upper()}")):
                return True
        return False
    
    def search_folder(folder: pathlib.Path, current_depth: int):
        """Recursively search for folders with HDR files."""
        if current_depth > max_depth:
            return
        
        try:
            for item in folder.iterdir():
                if not item.is_dir():
                    continue
                
                # Skip ignored folders
                if item.name in ignore_folders:
                    continue
                
                # Check if this folder has HDR files
                if has_hdr_files(item):
                    found_folders.append(item)
                
                # Recurse into subfolder
                search_folder(item, current_depth + 1)
        except PermissionError:
            pass  # Skip folders we can't access
    
    search_folder(folder_path, 1)
    return found_folders


def analyze_folders(folders: list) -> dict:
    """
    Analyze multiple folders and return their bracket/set counts.
    
    Args:
        folders: List of folder paths to analyze
    
    Returns:
        dict: Dictionary mapping folder paths to analysis result dicts
    """
    results = {}
    for folder_path in folders:
        results[folder_path] = analyze_folder(pathlib.Path(folder_path))
    return results


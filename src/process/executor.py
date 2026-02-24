"""
HDR Execution Module

Contains the main execution logic for batch processing HDR folders:
- HDRExecutor: Orchestrates the batch processing workflow
"""

import pathlib
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from time import sleep

from constants import VERBOSE
from utils.get_exif import get_exif
from src.config import CONFIG, SCRIPT_DIR

from utils.notify_phone import notify_phone
from utils.play_sound import play_sound
from utils.save_config import save_config
from process.hdr_processor import HDRProcessor


class HDRExecutor:
    """
    Orchestrates HDR batch processing workflow.
    
    This class handles:
    - Validating configuration and paths
    - Determining folders to process
    - Calculating total work for progress tracking
    - Managing the processing executor
    - Progress tracking and completion notifications
    """

    def __init__(
        self,
        batch_folders: list,
        folder_profiles: dict,
        extension: str,
        threads: int,
        do_align: bool,
        do_raw: bool,
        do_recursive: bool,
        progress_callback=None,
        completion_callback=None,
        log_callback=None,
    ):
        """
        Initialize the HDR executor.

        Args:
            batch_folders: List of folder paths to process
            folder_profiles: Dict mapping folder paths to PP3 profile names
            extension: File extension to process (.tif, .dng, etc.)
            threads: Number of worker threads
            do_align: Whether to align images before merging
            do_raw: Whether to process RAW files
            do_recursive: Whether to process subfolders recursively
            progress_callback: Callback for progress updates (value 0-100)
            completion_callback: Callback when processing completes
            log_callback: Callback for log messages
        """
        self.batch_folders = batch_folders
        self.folder_profiles = folder_profiles
        self.extension = extension
        self.threads = threads
        self.do_align = do_align
        self.do_raw = do_raw
        self.do_recursive = do_recursive
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback
        self.log_callback = log_callback
        
        self.processor = HDRProcessor(
            progress_callback=self._on_processor_progress,
            log_callback=self.log_callback,
        )
        self.total_sets_global = 0
        self.completed_sets_global = 0

    def _log(self, message):
        """Send log message to callback or print."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def _on_processor_progress(self, completed, total):
        """Handle progress updates from the processor."""
        self.completed_sets_global = completed
        self.total_sets_global = total
        if total > 0:
            progress = int((completed / total) * 100)
            if self.progress_callback:
                self.progress_callback(progress)

    def _get_profile_for_folder(self, folder_path: str, profiles: list) -> dict:
        """Get the PP3 profile for a folder."""
        if not profiles:
            return None

        folder_name = pathlib.Path(folder_path).name.lower()

        # Check if folder has a manually assigned profile
        if folder_path in self.folder_profiles:
            profile_name = self.folder_profiles[folder_path]
            for profile in profiles:
                if profile.get("name") == profile_name:
                    return profile

        # Try to auto-match by folder key
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

    def _determine_folders_to_process(self) -> list:
        """Determine all folders to process based on batch list and recursive setting."""
        folders_to_process = []

        for batch_folder_path in self.batch_folders:
            batch_folder = pathlib.Path(batch_folder_path)
            if not batch_folder.exists():
                self._log(
                    "Warning: Batch folder does not exist: %s" % batch_folder_path
                )
                continue
            
            if self.do_recursive:
                # Find all subfolders containing matching files
                glob = self.extension
                if "*" not in glob:
                    glob = "*%s" % glob
                for f in batch_folder.rglob(glob):
                    parent = f.parent
                    if parent not in folders_to_process and parent != batch_folder:
                        folders_to_process.append(parent)
                self._log(
                    "Batch folder '%s' (recursive): Found %d subfolders"
                    % (batch_folder_path, len([p for p in folders_to_process if str(p).startswith(str(batch_folder))]))
                )
            else:
                folders_to_process.append(batch_folder)
        
        self._log("Batch mode: Processing %d folders" % len(folders_to_process))
        for f in folders_to_process:
            self._log("  - %s" % f)
        
        return folders_to_process

    def _calculate_total_sets(self, folders_to_process: list, first_pass_extension: str) -> list:
        """
        Calculate total sets across all folders for progress tracking.
        
        Returns:
            list: List of tuples (folder, brackets, sets)
        """
        total_sets_global = 0
        folder_info = []

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

        self.total_sets_global = total_sets_global
        return folder_info

    def execute(self):
        """Execute the HDR batch processing."""
        folder_start_time = datetime.now()
        
        # Get executable paths from config
        EXE_PATHS = CONFIG.get("exe_paths", {})
        blender_exe = EXE_PATHS.get("blender_exe", "")
        luminance_cli_exe = EXE_PATHS.get("luminance_cli_exe", "")
        align_image_stack_exe = EXE_PATHS.get("align_image_stack_exe", "")
        rawtherapee_cli_exe = EXE_PATHS.get("rawtherapee_cli_exe", "")
        merge_blend = SCRIPT_DIR / "blender" / "HDR_Merge.blend"
        merge_py = SCRIPT_DIR / "blender" / "blender_merge.py"

        # Save GUI settings to config
        if self.do_raw:
            CONFIG["gui_settings"]["raw_extension"] = self.extension
            CONFIG["gui_settings"]["tif_extension"] = CONFIG.get("gui_settings", {}).get("tif_extension", ".tif")
        else:
            CONFIG["gui_settings"]["raw_extension"] = CONFIG.get("gui_settings", {}).get("raw_extension", ".dng")
            CONFIG["gui_settings"]["tif_extension"] = self.extension

        CONFIG["gui_settings"]["threads"] = str(self.threads)
        CONFIG["gui_settings"]["do_align"] = self.do_align
        CONFIG["gui_settings"]["do_recursive"] = self.do_recursive
        CONFIG["gui_settings"]["do_raw"] = self.do_raw
        save_config(CONFIG)

        original_extension = self.extension

        # Validate optional features
        optional_exes_available = CONFIG.get("_optional_exes_available", {})

        if self.do_align and not optional_exes_available.get("align_image_stack_exe", False):
            raise RuntimeError(
                "Align is enabled but align_image_stack is not configured or not found!\n\n"
                "Please configure the align_image_stack path in config.json."
            )

        # Determine folders to process
        folders_to_process = self._determine_folders_to_process()

        self._log("Starting [%s]..." % folder_start_time.strftime("%H:%M:%S"))

        # Determine extension for first pass
        if self.do_raw:
            raw_extension = self.extension
            if not raw_extension.startswith("."):
                raw_extension = "." + raw_extension
            if not raw_extension or raw_extension == ".":
                raw_extension = ".dng"
            first_pass_extension = raw_extension
        else:
            first_pass_extension = self.extension

        # Calculate total sets for progress tracking
        folder_info = self._calculate_total_sets(folders_to_process, first_pass_extension)

        # Check if any valid folders were found
        if not folder_info:
            self._log("No matching files found in the input folder.")
            raise RuntimeError("No matching files found")

        self._log("Total sets to process: %d" % self.total_sets_global)
        self.processor.set_progress_totals(self.total_sets_global)

        # Process all folders concurrently
        bracket_list = []
        total_sets = 0
        all_threads = []

        profiles = CONFIG.get("pp3_profiles", [])

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            # Submit all folder tasks
            for proc_folder, brackets, sets in folder_info:
                # Get folder-specific PP3 profile
                profile = self._get_profile_for_folder(str(proc_folder), profiles)
                folder_pp3_file = profile.get("path", "") if profile else ""

                brackets, sets, threads, error = self.processor.process_folder(
                    proc_folder,
                    blender_exe,
                    luminance_cli_exe,
                    align_image_stack_exe,
                    merge_blend,
                    merge_py,
                    original_extension,
                    self.do_align,
                    self.do_raw,
                    rawtherapee_cli_exe,
                    folder_pp3_file,
                    executor,
                )
                bracket_list.append(brackets)
                total_sets += sets
                all_threads.extend(threads)
                if error:
                    self._log("Error processing %s: %s" % (proc_folder, error))

            # Wait for all tasks to complete
            completed = set()
            while any(not t[1].done() for t in all_threads):
                sleep(1)
                for bracket_idx, tt in all_threads:
                    if not tt.done():
                        continue
                    if bracket_idx in completed:
                        continue
                    try:
                        tt.result()
                    except Exception as ex:
                        self._log("Bracket %d: Exception - %s" % (bracket_idx, ex))
                    completed.add(bracket_idx)

        self._log("Done!!!")
        folder_end_time = datetime.now()
        folder_duration = (folder_end_time - folder_start_time).total_seconds()
        self._log(
            "Total time: %.1f seconds (%.1f minutes)"
            % (folder_duration, folder_duration / 60)
        )
        self._log("Alignment: %s" % ("Yes" if self.do_align else "No"))
        self._log("Images per bracket: %s" % bracket_list)
        self._log("Total sets processed: %d" % total_sets)
        self._log("Threads used: %d" % self.threads)
        
        notify_phone(
            f"Completed processing folders: {', '.join([f.name for f in folders_to_process])}"
        )
        
        if self.completion_callback:
            self.completion_callback({
                "duration": folder_duration,
                "alignment": self.do_align,
                "bracket_list": bracket_list,
                "total_sets": total_sets,
                "threads": self.threads,
            })


def execute_hdr_processing(
    batch_folders: list,
    folder_profiles: dict,
    extension: str,
    threads: int,
    do_align: bool,
    do_raw: bool,
    do_recursive: bool,
    progress_callback=None,
    completion_callback=None,
    log_callback=None,
) -> threading.Thread:
    """
    Start HDR processing in a background thread.
    
    Args:
        batch_folders: List of folder paths to process
        folder_profiles: Dict mapping folder paths to PP3 profile names
        extension: File extension to process
        threads: Number of worker threads
        do_align: Whether to align images
        do_raw: Whether to process RAW files
        do_recursive: Whether to process subfolders recursively
        progress_callback: Callback for progress updates (value 0-100)
        completion_callback: Callback when processing completes
        log_callback: Callback for log messages
    
    Returns:
        threading.Thread: The background thread running the processing
    """
    executor = HDRExecutor(
        batch_folders=batch_folders,
        folder_profiles=folder_profiles,
        extension=extension,
        threads=threads,
        do_align=do_align,
        do_raw=do_raw,
        do_recursive=do_recursive,
        progress_callback=progress_callback,
        completion_callback=completion_callback,
        log_callback=log_callback,
    )
    
    thread = threading.Thread(target=executor.execute)
    return thread

"""
CLI Module for HDR Merge Master

Provides command-line interface for headless batch processing.
"""

import argparse
import json
import pathlib
import sys
from datetime import datetime

from process.executor import execute_hdr_processing
from process.folder_analyzer import analyze_folder, find_subfolders
from src.config import CONFIG
from utils.save_config import save_config


def load_batch_file(batch_path: str) -> list:
    """
    Load batch folder list from a JSON file.

    Args:
        batch_path: Path to the JSON batch file

    Returns:
        list: List of folder data dictionaries
    """
    batch_file = pathlib.Path(batch_path)
    if not batch_file.exists():
        raise FileNotFoundError(f"Batch file not found: {batch_path}")

    with open(batch_file, "r", encoding="utf-8") as f:
        batch_data = json.load(f)

    if "folders" not in batch_data:
        raise ValueError("Invalid batch file format: missing 'folders' key")

    return batch_data["folders"]


def add_folder_to_batch(
    folder_path: str,
    batch_list: list,
    profile: str = None,
    align: bool = False,
    recursive: bool = False,
) -> int:
    """
    Add a folder to the batch list with analysis.

    Args:
        folder_path: Path to the folder to add
        batch_list: Existing batch list to append to
        profile: Optional PP3 profile name
        align: Whether to enable alignment
        recursive: Whether to add subfolders recursively

    Returns:
        int: Number of folders added
    """
    folder = pathlib.Path(folder_path).absolute()
    if not folder.exists():
        print(f"Warning: Folder does not exist: {folder_path}")
        return 0

    if not folder.is_dir():
        print(f"Warning: Path is not a directory: {folder_path}")
        return 0

    added_count = 0

    if recursive:
        # Find all subfolders with HDR files
        gui_settings = CONFIG.get("gui_settings", {})
        max_depth = gui_settings.get("recursive_max_depth", 1)
        ignore_folders = gui_settings.get("recursive_ignore_folders", ["Merged"])

        subfolders = find_subfolders(folder, max_depth, ignore_folders)
        folders_to_add = [str(f.absolute()) for f in subfolders]
    else:
        folders_to_add = [str(folder)]

    for folder_path in folders_to_add:
        # Check if already in batch
        if any(f["path"] == folder_path for f in batch_list):
            continue

        # Analyze the folder
        analysis = analyze_folder(pathlib.Path(folder_path))

        folder_data = {
            "path": folder_path,
            "profile": profile or "",
            "align": align,
            "extension": analysis.get("extension", ".tif"),
            "is_raw": analysis.get("is_raw", False),
            "brackets": analysis.get("brackets", 0),
            "sets": analysis.get("sets", 0),
        }

        batch_list.append(folder_data)
        added_count += 1

    return added_count


def run_headless_processing(
    batch_list: list,
    threads: int = 6,
    recursive: bool = False,
    cleanup: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run HDR processing in headless mode.

    Args:
        batch_list: List of folder data dictionaries
        threads: Number of worker threads
        recursive: Whether to process subfolders recursively
        cleanup: Whether to cleanup temporary files
        verbose: Whether to print detailed progress

    Returns:
        dict: Processing results
    """
    from src.config import CONFIG

    print(f"\n{'='*60}")
    print("HDR Merge Master - Headless Processing")
    print(f"{'='*60}\n")

    # Validate batch list
    if not batch_list:
        print("Error: No folders to process!")
        return {"success": False, "error": "No folders to process"}

    # Build folder_data, folder_profiles, and folder_align from batch list
    folder_data = []
    folder_profiles = {}
    folder_align = {}

    for folder_info in batch_list:
        folder_path = folder_info.get("path")
        if not folder_path:
            continue

        folder_data.append(
            {
                "path": folder_path,
                "is_raw": folder_info.get("is_raw", False),
                "extension": folder_info.get("extension", ".tif"),
                "brackets": folder_info.get("brackets", 0),
                "sets": folder_info.get("sets", 0),
            }
        )

        # Only set profile if folder contains RAW files
        if folder_info.get("is_raw", False):
            profile = folder_info.get("profile", "")
            if profile:
                folder_profiles[folder_path] = profile

        folder_align[folder_path] = folder_info.get("align", False)

    if not folder_data:
        print("Error: No valid folders in batch list!")
        return {"success": False, "error": "No valid folders in batch list"}

    # Print processing summary
    print(f"Folders to process: {len(folder_data)}")
    print(f"Threads: {threads}")
    print(f"Cleanup: {'Yes' if cleanup else 'No'}")
    print(f"Align folders: {sum(1 for v in folder_align.values() if v)}")
    print()

    # Print folder details
    for fd in folder_data:
        folder_name = pathlib.Path(fd["path"]).name
        raw_status = "RAW" if fd["is_raw"] else "Processed"
        profile_info = f" (Profile: {folder_profiles.get(fd['path'], 'N/A')})" if fd["is_raw"] else ""
        align_info = " [Align]" if folder_align.get(fd["path"], False) else ""
        print(f"  - {folder_name}: {fd['sets']} sets, {fd['brackets']} brackets ({raw_status}){profile_info}{align_info}")

    print(f"\nStarting processing at {datetime.now().strftime('%H:%M:%S')}...\n")

    # Track progress
    last_progress = -1

    def progress_callback(value):
        nonlocal last_progress
        if value != last_progress:
            print(f"Progress: {value}%")
            last_progress = value

    def log_callback(message):
        if verbose:
            print(message)
        else:
            # Print only important messages
            if any(keyword in message.lower() for keyword in ["error", "done", "total", "starting"]):
                print(message)

    results = {}

    def completion_callback(result_data):
        nonlocal results
        results = result_data

    # Start processing
    processing_thread = execute_hdr_processing(
        folder_data=folder_data,
        folder_profiles=folder_profiles,
        folder_align=folder_align,
        threads=threads,
        do_recursive=recursive,
        progress_callback=progress_callback,
        completion_callback=completion_callback,
        log_callback=log_callback,
    )

    # Start the thread and wait for completion
    processing_thread.start()
    processing_thread.join()

    if results:
        print(f"\n{'='*60}")
        print("Processing Complete!")
        print(f"{'='*60}")
        print(f"Duration: {results.get('duration', 0):.1f} seconds")
        print(f"Total sets processed: {results.get('total_sets', 0)}")
        print(f"Threads used: {results.get('threads', threads)}")
        print(f"{'='*60}\n")
        return {"success": True, **results}
    else:
        print("\nError: Processing completed without results!")
        return {"success": False, "error": "Processing completed without results"}


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="HDR Merge Master - Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --cli -b batch.json
  %(prog)s --cli -f /path/to/images -t 8
  %(prog)s --cli -f /path/to/images -a -p "My Profile"
  %(prog)s --cli -b batch.json -c -v
        """,
    )

    # CLI mode flag
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in headless CLI mode (no GUI)",
    )

    # Batch file option
    parser.add_argument(
        "-b", "--batch",
        metavar="FILE",
        help="Load batch folder list from a JSON file",
    )

    # Single folder option
    parser.add_argument(
        "-f", "--folder",
        metavar="PATH",
        help="Add a single folder to process",
    )

    # Recursive option for --folder
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Process subfolders recursively (with --folder)",
    )

    # Profile option
    parser.add_argument(
        "-p", "--profile",
        metavar="NAME",
        help="PP3 profile name to use (for RAW files)",
    )

    # Align option
    parser.add_argument(
        "-a", "--align",
        action="store_true",
        help="Enable image alignment",
    )

    # Threads option
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=6,
        metavar="N",
        help="Number of worker threads (default: 6)",
    )

    # Cleanup option
    parser.add_argument(
        "-c", "--cleanup",
        action="store_true",
        help="Cleanup temporary files after processing",
    )

    # Verbose option
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed progress information",
    )

    args = parser.parse_args()

    # If not in CLI mode, show help or let GUI handle it
    if not args.cli:
        parser.print_help()
        return

    # Validate arguments
    if not args.batch and not args.folder:
        print("Error: Must specify either --batch or --folder")
        parser.print_help()
        sys.exit(1)

    # Build batch list
    batch_list = []

    # Load from batch file if specified
    if args.batch:
        try:
            batch_list = load_batch_file(args.batch)
            print(f"Loaded {len(batch_list)} folders from: {args.batch}")
        except Exception as e:
            print(f"Error loading batch file: {e}")
            sys.exit(1)

    # Add single folder if specified
    if args.folder:
        added = add_folder_to_batch(
            args.folder,
            batch_list,
            profile=args.profile,
            align=args.align,
            recursive=args.recursive,
        )
        print(f"Added {added} folder(s): {args.folder}")

    # Run headless processing
    results = run_headless_processing(
        batch_list=batch_list,
        threads=args.threads,
        recursive=args.recursive,
        cleanup=args.cleanup,
        verbose=args.verbose,
    )

    # Exit with appropriate code
    sys.exit(0 if results.get("success", False) else 1)


if __name__ == "__main__":
    main()

import sys


def get_default_config() -> dict:
    """Get default configuration with OS-specific paths."""
    if sys.platform.startswith("win"):
        # Windows default paths
        default_exe_paths = {
            "align_image_stack_exe": "C:\\Program Files\\Hugin\\bin\\align_image_stack.exe",
            "blender_exe": "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe",
            "luminance_cli_exe": "C:\\Program Files\\Luminance HDR\\v.2.6.0\\luminance-hdr-cli.exe",
            "rawtherapee_cli_exe": "C:\\Program Files\\RawTherapee\\5.12\\rawtherapee-cli.exe",
        }
    else:
        # Linux default paths
        default_exe_paths = {
            "align_image_stack_exe": "/usr/bin/align_image_stack",
            "blender_exe": "/usr/bin/blender",
            "luminance_cli_exe": "/usr/bin/luminance-hdr-cli",
            "rawtherapee_cli_exe": "/usr/bin/rawtherapee-cli",
        }

    return {
        "exe_paths": default_exe_paths,
        "gui_settings": {
            "raw_extensions": [".dng", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".orf", ".rw2", ".pef"],
            "processed_extensions": [".tif", ".tiff", ".png"],
            "threads": "6",
            "do_align": False,
            "use_opencv": False,
            "do_cleanup": False,
            "do_recursive": False,
            "recursive_max_depth": 1,
            "recursive_ignore_folders": ["Merged", "tif", "exr", "jpg", "aligned"],
            "do_raw": False,
            "pp3_file": "",
        },
        "pp3_profiles": [],
    }
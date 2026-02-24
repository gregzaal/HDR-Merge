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
            "raw_extension": ".dng",
            "tif_extension": ".tif",
            "threads": "6",
            "do_align": False,
            "do_recursive": False,
            "do_raw": False,
            "pp3_file": "",
        },
        "pp3_profiles": [],
    }
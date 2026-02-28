# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

# nuitka-project: --mode=onefile
# nuitka-project: --assume-yes-for-downloads
# nuitka-project: --output-filename=hdr-brackets-cli
# nuitka-project: --output-dir=build

"""
CLI-only entry point for HDR Merge Master.

This module provides a clean entry point for command-line usage
without any GUI dependencies.
"""

from cli import main

if __name__ == "__main__":
    main()

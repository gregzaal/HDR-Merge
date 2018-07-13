# HDR-Merge

A script that uses Blender's compositor to reliably merge exposure brackets to a 32-bit EXR file.

## Requirements

* [Python 3.5](https://www.python.org/downloads/release/python-354/)
* Blender ([2.78](http://download.blender.org/release/Blender2.78/) or [2.79](http://download.blender.org/release/Blender2.79/) recommended)
* [Luminance HDR](http://qtpfsgui.sourceforge.net/?page_id=10) (tested with [2.4.0](https://sourceforge.net/projects/qtpfsgui/files/luminance/2.4.0/))

Only tested on windows, but *should* work on linux/mac.

### Python Libraries

This script uses the PyQT4 module for the interface, and ExifRead for detecting exposure sets from photo metadata.

PyQT4 can be installed by downloading the appropriate `whl` file [here](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyqt4) (e.g. for Python 3.5.x Windows 64 bit, it's `PyQt4‑4.11.4‑cp35‑cp35m‑win_amd64.whl`) and install it using `pip install PyQt4‑4.11.4‑cp35‑cp35m‑win_amd64.whl`.

ExifRead can be installed with just `pip install exifread`.

## Usage

Running the script for the first time will prompt you to edit `exe_paths.json` to fill in the paths to your `blender.exe` and `luminance-hdr-cli.exe` executable files.

1. Select a folder that contains your full set of exposure brackets (see *Example Folder Structure* below)
2. Choose a pattern to match the files (e.g. `.tif` to get all TIFF files). All formats that Blender supports should work. Raw files from your camera wont work, so I typically do some minor tweaks to them in Lightroom first (e.g. chromatic aberration correction) and then export 16-bit .tif files.
3. Choose the number of threads - this is the number of simultaneous bracketed exposures to merge. This affects processing speed, but not linearly. Use as many threads as you can without running out of RAM - start with 2 or 3 and monitor RAM usage.
4. Filters - meant to compensate for color casts introduced by ND filters, but currently not implemented for mainstream use. I've only implemented my own two filters, so just leave this at "None" for now.
5. Click *Create HDRs*, and monitor the console window for progress and errors

## Example Folder Structure

The folder you select should contain all the photos you took when shooting. The script will automatically read the metadata and determine which images should be grouped together and merged.

Exposures must always be decending or ascending (`0 + ++` or `0 - --`, never `- 0 +` or `0 + -`).

For example:

* C:/Foo/bar/
    * `IMG001.tif` - 1/4000 F/8 ISO100
    * `IMG002.tif` - 1/1000 F/8 ISO200
    * `IMG003.tif` - 1/250 F/8 ISO400
    * `IMG004.tif` - 1/4000 F/8 ISO100
    * `IMG005.tif` - 1/1000 F/8 ISO200
    * `IMG006.tif` - 1/250 F/8 ISO400

The script will discover that images `IMG001.tif` and `IMG004.tif` have the same exposure settings, and thus the images will be grouped into threes:

* Exposure set 1 (merged to `merged_000.exr`):
    * `IMG001.tif`
    * `IMG002.tif`
    * `IMG003.tif`
* Exposure set 2 (merged to `merged_001.exr`):
    * `IMG004.tif`
    * `IMG005.tif`
    * `IMG006.tif`

## TODO

* Don't use PyQT. Installation is not reliable, rather use Tk.
* Support arbitrary user-created ND filter compensations.
* Allow for inconsistant exposure brackets - currently the first exposure set determines how many images there are per set, but it should be possible to support exposure sets with varying numbers of images.
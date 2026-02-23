# HDR-Merge

A script that uses Blender's compositor to reliably merge exposure brackets to 32-bit EXR files in bulk.

<p align="center">
<img width="452" height="118" alt="2026-02-23_14-58-45" src="https://github.com/user-attachments/assets/ff359f04-d101-4eee-9835-e92f94ec9659" />
</p>

## Installation

Requires:

* [Blender 2.79](http://download.blender.org/release/Blender2.79/)
* [Luminance HDR v2.4.0](https://sourceforge.net/projects/qtpfsgui/files/luminance/2.4.0/) (later versions will not work)
* [Hugin 2021](https://hugin.sourceforge.io/download/)

1. Install the required software above.
2. [Download](https://github.com/gregzaal/HDR-Merge/archive/master.zip) or [clone](git@github.com:gregzaal/HDR-Merge.git) this repository.
3. Build the executable with `build.bat` (Windows only).
4. Run `build/hdr_brackets.dist/hdr_brackets.exe`, **OR** run the `hdr_brackets.py` script using the instructions below.

### Run From Source (optional)

This program is a simple python script that can be run straight from the `.py` script if you can't or don't want to use the pre-built executable. It has only been tested on windows, but *should* work on linux/mac too.

You will need:

* [Python 3.5](https://www.python.org/downloads/release/python-354/)
* ExifRead python library - install with `pip install exifread`
* Notification library: `pip install plyer`

## Usage

Running the script for the first time will prompt you to edit `exe_paths.json` to fill in the paths to your `blender.exe`, `luminance-hdr-cli.exe` and `align_image_stack.exe` executable files. It should look something like this (note the double backslashes; you can use forward slashes as well):

```
{
    "blender_exe": "C:\\Program Files\\Blender 2.79\\blender.exe",
    "luminance_cli_exe": "C:\\Program Files\\LuminanceHDR\\luminance-hdr-cli.exe",
    "align_image_stack_exe": "C:\\Program Files\\Hugin\\bin\\align_image_stack.exe"
}
```

Note: Do not use the `align_image_stack.exe` that comes with LuminanceHDR, as this is a different version which won't work. Only use the one that comes with Hugin itself.

Then:

1. Select a folder that contains your full set of exposure brackets (see *Example Folder Structure* below)
2. Choose a pattern to match the files (e.g. `.tif` to get all TIFF files). All formats that Blender supports should work, but **RAW files from your camera will not work**. I typically do some minor tweaks to the RAW files in Lightroom first (e.g. chromatic aberration correction) and then export 16-bit `.tif` files to merge with this script.
3. Choose the number of threads (the number of simultaneous bracketed exposures to merge). Use as many threads as you can without running out of RAM or freezing your computer. In my experience 6 threads usually works fine for 32 GB RAM.
4. Click *Create HDRs*, and monitor the console window for progress and errors.
5. The merged HDR images will be in a folder called `Merged` next to your original files. The `exr` subfolder contains the actual 32-bit HDR files, while the `jpg` folder contains tonemapped versions of those files.

Note: This tool does not do any ghost removal, so it's important that you use a steady tripod when shooting.

The intended use here is for creating HDRIs, allowing you to stitch with the JPG files (which load quickly and, being tonemapped, show more dynamic range), and then swap the JPGs out with the EXR files at the end before your final export. If you are using PTGui, you can do this using the included `ptgui_jpg_to_hdr.py` file - just drag your `.pts` project file onto that script and it will replace the JPG paths with EXR ones.

## Example Input Folder Structure

The script will automatically read the metadata and determine which images should be grouped together and merged. The entire folder of images will be merged based on the pattern determined by the first set.

The bracket matching works by checking the exposure metadata of the first image and searching for the next image with the same exposure:

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

Exposures can be in any order (`0 + ++`, `0 - --`, `0 + -`, `- 0 +`, etc.).

## TODO

* Allow for inconsistant exposure brackets - currently the first exposure set determines how many images there are per set, but it should be possible to support exposure sets with varying numbers of images.

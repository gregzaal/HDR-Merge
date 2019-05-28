# HDR-Merge

A script that uses Blender's compositor to reliably merge exposure brackets to 32-bit EXR files in bulk.

![screenshot](https://raw.githubusercontent.com/gregzaal/HDR-Merge/master/icons/screenshot.png)

## Installation

Requires:

* [Blender 2.79](http://download.blender.org/release/Blender2.79/)
* [Luminance HDR v2.4.0](https://sourceforge.net/projects/qtpfsgui/files/luminance/2.4.0/) (later versions will not work)

1. Install the required software above.
2. [Download](https://github.com/gregzaal/HDR-Merge/archive/master.zip) or [clone](git@github.com:gregzaal/HDR-Merge.git) this repository. 
3. Run the executable `build/hdr_brackets.exe` (Windows only), **OR** run the `hdr_brackets.py` script using the instructions below.

### Run From Source (optional)

This program is a simple python script that can be run straight from the `.py` script if you can't or don't want to use the pre-built executable. It has only been tested on windows, but *should* work on linux/mac too.

You will need:

* [Python 3.5](https://www.python.org/downloads/release/python-354/)
* ExifRead python library - install with `pip install exifread`

## Usage

Running the script for the first time will prompt you to edit `exe_paths.json` to fill in the paths to your `blender.exe` and `luminance-hdr-cli.exe` executable files. It should look something like this:

```
{
    "blender_exe": "C:\Program Files\Blender 2.79\blender.exe",
    "luminance_cli_exe": "C:\Program Files\LuminanceHDR\luminance-hdr-cli.exe"
}
```

Then:

1. Select a folder that contains your full set of exposure brackets (see *Example Folder Structure* below)
2. Choose a pattern to match the files (e.g. `.tif` to get all TIFF files). All formats that Blender supports should work, but **RAW files from your camera will not work**. I typically do some minor tweaks to the RAW files in Lightroom first (e.g. chromatic aberration correction) and then export 16-bit `.tif` files to merge with this script.
3. Choose the number of threads (the number of simultaneous bracketed exposures to merge). Use as many threads as you can without running out of RAM or freezing your computer. In my experience 6 threads usually works fine for 32 GB RAM.
4. Click *Create HDRs*, and monitor the console window for progress and errors.
5. The merged HDR images will be in a folder called `Merged` next to your original files. The `exr` subfolder contains the actual 32-bit HDR files, while the `jpg` folder contains tonemapped versions of those files.

Note: This tool does not do any alignment or ghost removal, so it's important that you use a steady tripod when shooting.

The intended use here is for creating HDRIs, allowing you to stitch with the JPG files (which load quickly and, being tonemapped, show more dynamic range), and then swap the JPGs out with the EXR files at the end before your final export. If you are using PTGui, you can do this using the included `ptgui_jpg_to_hdr.py` file - just drag your `.pts` project file onto that script and it will replace the JPG paths with EXR ones.

## Example Input Folder Structure

All the input files must be in the same folder. The script will automatically read the metadata and determine which images should be grouped together and merged.

Exposures must always be decending or ascending (`0 + ++` or `0 - --`, never `0 + -`).

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

* Allow for inconsistant exposure brackets - currently the first exposure set determines how many images there are per set, but it should be possible to support exposure sets with varying numbers of images.
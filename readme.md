# HDR Merge Master

A script that uses Blender's compositor to reliably merge exposure brackets to 32-bit EXR files in bulk.

<p align="center">
<img width="841" height="466" alt="Screenshot 2026-03-31 174225" src="https://github.com/user-attachments/assets/013e260e-e3ef-4658-8a98-4407feca36a6" />
</p>

This tool is used at [Poly Haven](https://polyhaven.com/hdris) to merge exposure bracket sequences for HDRI creation. Read more about our HDRI workflow [on our blog](https://blog.polyhaven.com/how-to-create-high-quality-hdri/).


## Installation

#### Requires:

* [Blender 4.5 LTS](https://www.blender.org/download/releases/4-5/)

#### Optional:

* [Luminance HDR v2.6.1](https://sourceforge.net/projects/qtpfsgui/files/luminance/) (JPG preview) - not needed on Blender 5.0+, which tonemaps the JPG preview itself; only required as a fallback there, or as the sole JPG source on older Blender versions.
* [Hugin 2021](https://hugin.sourceforge.io/download/) (aligning images) - some builds bundle `align_image_stack.exe` already; see *Bundling align_image_stack* below.
* [Rawtherapee](https://rawtherapee.com/downloads/5.12/) (processing from raw files)

1. Install the required software above.
2. If the optional software is not installed, the relevant options will be disabled
2. [Download the latest release](https://github.com/gregzaal/HDR-Merge-Master/releases) and run `hdr_merge_master.exe`

#### Bundling align_image_stack

A build can bundle its own copy of `align_image_stack.exe`/`align_image_stack` so users don't need to install Hugin separately. Drop the binary (plus its license text) into `vendor/win/` or `vendor/linux/` - see `vendor/README.md` for the exact expected filenames. If present, it's picked up automatically with no config changes needed; otherwise the app falls back to whatever path is configured in Setup.

### Run From Source (optional)

#### Prerequisites

Ensure you have uv installed. If you don't have it yet:

Windows:
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
macOS/Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Clone the Repository

```bash
git clone https://github.com/gregzaal/HDR-Merge-Master.git
cd HDR-Merge-Master
```

#### Run the Application

You do not need to manually create a virtual environment or install dependencies. Simply run:
```bash
uv run python hdr_brackets.py
```
uv will automatically create a .venv, install the correct Python version (3.12+), and fetch all dependencies defined in pyproject.toml before launching the app.

## Usage

Running for the first time will prompt you to locate the `.exe` files for the software above (`blender.exe` is required, the rest are optional).

Note: Do not use the `align_image_stack.exe` that comes with LuminanceHDR, as this is a different version which won't work. Only use the one that comes with Hugin itself.

Then:

1. Select a folder that contains your full set of exposure brackets (see *Example Folder Structure* below). You can now add multiple folders to the input folders for batch processing. You can also paste a folder path from the clipboard with **Ctrl+V** instead of using the file browser.
2. Choose a pattern to match the files (e.g. `.tif` to get all TIFF files). All formats that Blender supports should work, but if you want to use RAW files from your camera, **you need to install RawTherapee and enable the RAW option in the UI**. I typically do some minor tweaks to the RAW files in RawTherapee first (e.g. chromatic aberration correction) and then export 16-bit `.tif` files to merge with this script. If a `.pp3` file already exists next to the RAW files themselves, it's used automatically instead of a managed profile - you can still override this per folder from the profile dropdown.
3. Choose the number of threads (the number of simultaneous bracketed exposures to merge). Use as many threads as you can without running out of RAM or freezing your computer. In my experience 6 threads usually works fine for 32 GB RAM, but this depends on your camera resolution.
4. Choose an alignment mode for the selected folder: **None** (no alignment; Translate nodes are still added in Blender so you can adjust alignment manually afterwards), **Hugin** (external pre-align via `align_image_stack`), or **MTB** (alignment computed inside Blender via OpenCV, default). These are mutually exclusive per folder.
5. Choose the output format for the merged images: **EXR** (32-bit OpenEXR, default) or **HDR** (Radiance). This applies to the whole batch and requires Blender 5.0+ (blender_merge_5.0.py).
6. The "Recursive" option will iterate through all subfolders of your selected folder.
7. Click *Create HDRs*, and monitor the console window for progress and errors.
8. The merged HDR images will be in a folder called `Merged` next to your original files. The `exr` subfolder contains the actual 32-bit HDR files (or Radiance `.hdr` files if that output format was chosen), while the `jpg` folder contains tonemapped versions of those files. On Blender 5.0+, the JPG is tonemapped directly inside Blender's compositor (no separate Luminance HDR call); it automatically falls back to `luminance-hdr-cli.exe` if that doesn't produce a file.

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

If the automatic detection gets the number of images per bracket wrong, you can override it manually: double-click the **Brackets** cell for that folder in the batch table and type the correct count. The **Sets** count updates automatically, and only complete sets (i.e. a multiple of the specified bracket count) will be merged - any leftover images at the end of the folder are skipped.

## Command Line Interface (CLI)

The application supports a headless CLI mode for automated batch processing without the GUI.

**Basic Usage:**

```bash
python hdr_brackets.py --cli [options]
```

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--cli` | | Run in headless CLI mode (no GUI) |
| `--batch <FILE>` | `-b` | Load batch folder list from a JSON file |
| `--folder <PATH>` | `-f` | Add a single folder to process |
| `--recursive` | `-r` | Process subfolders recursively (with `--folder`) |
| `--profile <NAME>` | `-p` | PP3 profile name to use (for RAW files) |
| `--align` | `-a` | Enable Hugin-based alignment (shorthand for `--align-mode hugin`) |
| `--align-mode <MODE>` | | Alignment mode: `none`, `hugin`, or `mtb` (default: `mtb`). Mutually exclusive; overrides `--align` |
| `--threads <N>` | `-t` | Number of worker threads (default: 6) |
| `--cleanup` | `-c` | Cleanup temporary files after processing |
| `--verbose` | `-v` | Print detailed progress information |

**Examples:**

```bash
# Process folders from a batch JSON file
python hdr_brackets.py --cli --batch batch.json
python hdr_brackets.py --cli -b batch.json

# Process a single folder with default settings
python hdr_brackets.py --cli --folder /path/to/images
python hdr_brackets.py --cli -f /path/to/images

# Process a folder with alignment and custom profile
python hdr_brackets.py --cli --folder /path/to/images --align --profile "My Profile"
python hdr_brackets.py --cli -f /path/to/images -a -p "My Profile"

# Process with more threads and cleanup
python hdr_brackets.py --cli --batch batch.json --threads 8 --cleanup
python hdr_brackets.py --cli -b batch.json -t 8 -c

# Process folder recursively with verbose output
python hdr_brackets.py --cli --folder /path/to/images --recursive --verbose
python hdr_brackets.py --cli -f /path/to/images -r -v
```

**Batch JSON File Format:**

You can export and import batch lists from the GUI using the Export/Import buttons. The JSON format is:

```json
{
  "version": "0.1.0",
  "folders": [
    {
      "path": "C:/Images/Folder1",
      "profile": "My Profile",
      "align": true,
      "mtb_align": false,
      "extension": ".tif",
      "is_raw": false,
      "brackets": 3,
      "sets": 10,
      "file_count": 30,
      "brackets_override": null
    }
  ]
}
```

Note: `align` (Hugin, external pre-align) and `mtb_align` (MTB, inside Blender) are mutually exclusive per folder. If both are omitted, `mtb_align` defaults to `true`.

Note: `brackets_override`, when set to a number, forces that many images per bracket instead of auto-detecting from EXIF data (see *Example Input Folder Structure* above).

Note: In CLI mode, processing begins automatically once all folders are loaded.

## Bulding

### Manual offline builds
The distribution can be built using:

`uv run python -m nuitka hdr_brackets.py `

hdr_brackets.py has nuitka options preconfigured inside of it, so appropriate
The build will be located inside /build

### Github Actions Build

1. Update your version in pyproject.toml (e.g., to 0.1.4).

2. Tag your commit in your terminal:
```Bash
git add .
git commit -m "Prepare release v0.1.4"
git tag v0.1.4
git push origin main --tags
```

4. This will add a new tag to the project and will trigger the action to make a build

import exifread


import pathlib


def get_exif(filepath: pathlib.Path):
    with filepath.open("rb") as f:
        tags = exifread.process_file(f)

    # Try different possible EXIF tag names for image dimensions
    try:
        width = str(tags["Image ImageWidth"])
        height = str(tags["Image ImageLength"])
    except KeyError:
        try:
            width = str(tags["EXIF ExifImageWidth"])
            height = str(tags["EXIF ExifImageLength"])
        except KeyError:
            raise RuntimeError("Could not find image dimensions in EXIF data")

    resolution = width + "x" + height
    shutter_speed = eval(str(tags["EXIF ExposureTime"]))
    try:
        aperture = eval(str(tags["EXIF FNumber"]))
    except ZeroDivisionError:
        aperture = 0
    iso = int(str(tags["EXIF ISOSpeedRatings"]))
    return {
        "resolution": resolution,
        "shutter_speed": shutter_speed,
        "aperture": aperture,
        "iso": iso,
    }
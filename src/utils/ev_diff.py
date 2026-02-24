from math import log


def ev_diff(bright_image, dark_image):
    dr_shutter = log(bright_image["shutter_speed"] / dark_image["shutter_speed"], 2)
    try:
        dr_aperture = log(dark_image["aperture"] / bright_image["aperture"], 1.41421)
    except (ValueError, ZeroDivisionError):
        # No lens data means aperture is 0, and we can't divide by 0 :)
        dr_aperture = 0
    dr_iso = log(bright_image["iso"] / dark_image["iso"], 2)
    return dr_shutter + dr_aperture + dr_iso
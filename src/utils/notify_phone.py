from config import SCRIPT_DIR


import sys


def notify_phone(msg="Done"):
    message = str(msg)
    icon_dir = SCRIPT_DIR / "icons"
    try:
        notification = __import__("plyer", fromlist=["notification"]).notification
    except ImportError as ex:
        raise RuntimeError(
            "Missing required dependency 'plyer'. Install it with: pip install plyer"
        ) from ex

    notify_kwargs = {
        "title": "HDR Merge Master",
        "message": message,
        "app_name": "HDR Merge Master",
        "timeout": 30,
    }

    if sys.platform.startswith("win"):
        icon_candidates = [icon_dir / "icon.ico", icon_dir / "icon.png"]
    else:
        icon_candidates = [icon_dir / "icon.png", icon_dir / "icon.ico"]

    last_exception = None
    for icon_path in icon_candidates:
        if not icon_path.exists():
            continue
        try:
            notification.notify(**{**notify_kwargs, "app_icon": icon_path.as_posix()})
            return
        except Exception as ex:
            last_exception = ex

    try:
        notification.notify(**notify_kwargs)
    except Exception as ex:
        if last_exception is not None:
            raise RuntimeError("Failed to send system notification") from last_exception
        raise RuntimeError("Failed to send system notification") from ex
# vendor/

Drop-in location for third-party executables to bundle into the standalone
build, so end users don't need to install them separately.

Currently supported:

- `vendor/win/align_image_stack.exe` (+ any DLLs it needs)
- `vendor/linux/align_image_stack`

If a binary is present at one of these paths, `src/utils/get_config.py` will
use it automatically as a fallback whenever no working user-configured
`align_image_stack_exe` path is set - no further code changes needed.

`align_image_stack` is part of [Hugin](https://hugin.sourceforge.io/) and is
GPL-licensed. If you vendor it, also include Hugin's license text
(`vendor/win/LICENSE` / `vendor/linux/LICENSE`) alongside the binary - it gets
picked up by the same `--include-data-dir=vendor/=vendor/` Nuitka directive
in `hdr_brackets.py`.

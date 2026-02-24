import json
import pathlib


def read_json(fp: pathlib.Path) -> dict:
    with fp.open("r") as f:
        s = f.read()
        # Work around invalid JSON when people paste single backslashes in there.
        s = s.replace("\\", "/")
        try:
            return json.loads(s)
        except json.JSONDecodeError as ex:
            raise RuntimeError("Error reading JSON from %s: %s" % (fp, ex))
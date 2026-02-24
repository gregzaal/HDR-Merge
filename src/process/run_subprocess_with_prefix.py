import pathlib
import subprocess
from datetime import datetime


def run_subprocess_with_prefix(
    cmd: list, bracket_id: int, label: str, out_folder: pathlib.Path
):
    """Run a subprocess and save output to a timestamped log file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = "bracket_%03d_%s_%s.log" % (bracket_id, label, timestamp)
    log_path = out_folder / "logs" / log_filename
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as log_file:
        result = subprocess.run(cmd, capture_output=True, text=True)
        log_file.write("STDOUT:\n")
        log_file.write(result.stdout)
        log_file.write("\nSTDERR:\n")
        log_file.write(result.stderr)

    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
"""
HDR Processor Module

Contains core processing logic for HDR image merging:
- process_raw_with_rawtherapee: Process RAW files using RawTherapee CLI
- do_merge: Merge bracketed images into HDR using Blender
- process_folder: Process a single folder of images
"""

import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from constants import VERBOSE
from process.run_subprocess_with_prefix import run_subprocess_with_prefix
from src.config import CONFIG
from utils.chunks import chunks
from utils.ev_diff import ev_diff
from utils.get_exif import get_exif


class HDRProcessor:
    """Handles all HDR processing operations."""

    def __init__(self, progress_callback=None, log_callback=None):
        """
        Initialize the HDR processor.

        Args:
            progress_callback: Optional callback for progress updates (completed, total)
            log_callback: Optional callback for log messages
        """
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.completed_sets_global = 0
        self.total_sets_global = 0

    def _log(self, message):
        """Send log message to callback or print."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def _update_progress(self):
        """Update progress via callback."""
        if self.progress_callback:
            self.progress_callback(self.completed_sets_global, self.total_sets_global)

    def process_raw_with_rawtherapee(
        self,
        rawtherapee_cli_exe: str,
        pp3_file: str,
        folder: pathlib.Path,
        extension: str,
        executor: ThreadPoolExecutor,
    ) -> pathlib.Path:
        """Process RAW files in folder using RawTherapee CLI and output TIFFs to a 'tif' subfolder."""
        self._log("\nFolder %s: Processing RAW files with RawTherapee..." % folder.name)

        # Determine RAW file extension (default to .dng)
        raw_extension = extension if extension.startswith(".") else "." + extension
        if not raw_extension:
            raw_extension = ".dng"

        # Find all RAW files in the folder
        glob_pattern = "*%s" % raw_extension
        raw_files = list(folder.glob(glob_pattern))

        if not raw_files:
            self._log(
                "Folder %s: No RAW files found with pattern '%s'"
                % (folder.name, glob_pattern)
            )
            return None

        # Create output folder for TIFFs
        tif_folder = folder / "tif"
        tif_folder.mkdir(parents=True, exist_ok=True)

        self._log(
            "Folder %s: Running RawTherapee CLI in parallel on %d RAW files..."
            % (folder.name, len(raw_files))
        )

        futures = []
        for idx, raw_file in enumerate(raw_files):
            cmd = [
                rawtherapee_cli_exe,
                "-p",
                pp3_file,
                "-o",
                str(tif_folder),
                "-t",
                "-c",
                str(raw_file),
            ]
            if VERBOSE:
                self._log(
                    "Folder %s: RAW %d/%d command: %s"
                    % (folder.name, idx + 1, len(raw_files), " ".join(cmd))
                )
            futures.append(
                (idx, raw_file, executor.submit(
                    run_subprocess_with_prefix,
                    cmd,
                    idx,
                    "rawtherapee",
                    tif_folder,
                ))
            )

        failures = []
        future_to_job = {future: (idx, raw_file) for idx, raw_file, future in futures}
        for future in as_completed(future_to_job):
            idx, raw_file = future_to_job[future]
            try:
                future.result()
            except Exception as ex:
                failures.append((idx, raw_file, ex))

        if failures:
            first_idx, first_file, first_ex = failures[0]
            self._log(
                "Folder %s: Failed RAW conversion for %d/%d file(s). First failure: #%d %s (%s)"
                % (
                    folder.name,
                    len(failures),
                    len(raw_files),
                    first_idx + 1,
                    first_file.name,
                    first_ex,
                )
            )
            raise first_ex

        self._log(
            "Folder %s: RawTherapee processing complete. TIFFs saved to: %s"
            % (folder.name, tif_folder)
        )
        return tif_folder

    def do_merge(
        self,
        blender_exe: str,
        merge_blend: pathlib.Path,
        merge_py: pathlib.Path,
        exifs,
        out_folder: pathlib.Path,
        filter_used,
        i,
        img_list,
        folder: pathlib.Path,
        luminance_cli_exe,
        align_image_stack_exe,
        do_align: bool,
        do_mtb_align: bool,
        output_format: str = "exr",
    ):
        """Merge a bracket set into an HDR image."""
        exr_folder = out_folder / "exr"
        jpg_folder = out_folder / "jpg"
        align_folder = out_folder / "aligned"

        exr_folder.mkdir(parents=True, exist_ok=True)
        jpg_folder.mkdir(parents=True, exist_ok=True)

        out_suffix = ".hdr" if output_format == "hdr" else ".exr"
        exr_path = exr_folder / ("merged_%03d%s" % (i, out_suffix))
        jpg_path = jpg_folder / exr_path.with_suffix(".jpg").name

        if exr_path.exists():
            print(
                "Folder %s: Bracket %d: Skipping, %s exists"
                % (folder.name, i, exr_path.relative_to(folder))
            )
        else:
            if do_align:
                if VERBOSE:
                    print(
                        "Folder %s: Bracket %d: Aligning images %s"
                        % (folder.name, i, [pathlib.Path(p.split("___")[0]).name for p in img_list])
                    )
                else:
                    print("Folder %s: Bracket %d: Aligning images" % (folder.name, i))

                align_folder.mkdir(parents=True, exist_ok=True)
                actual_img_list = [i.split("___")[0] for i in img_list]
                cmd = [
                    align_image_stack_exe,
                    "-v",
                    "-i",
                    "-l",
                    "-a",
                    (align_folder / "align_{}_".format(i)).as_posix(),
                    "--gpu",
                ]
                cmd += actual_img_list
                new_img_list = []
                for j, img in enumerate(img_list):
                    new_img_list.append(
                        (
                            align_folder
                            / "align_{}_{}.tif___{}".format(
                                i, str(j).zfill(4), img_list[j].split("___")[-1]
                            )
                        ).as_posix()
                    )
                run_subprocess_with_prefix(cmd, i, "align", out_folder)
                img_list = new_img_list

            if VERBOSE:
                print(
                    "Folder %s: Bracket %d: Merging %s"
                    % (folder.name, i, [pathlib.Path(p.split("___")[0]).name for p in img_list])
                )
            else:
                print("Folder %s: Bracket %d: Merging" % (folder.name, i))

            cmd = [
                blender_exe,
                "--background",
                merge_blend.as_posix(),
                "--factory-startup",
                "--python",
                merge_py.as_posix(),
                "--",
                exifs[0]["resolution"],
                exr_path.as_posix(),
                filter_used,
                str(i),
            ]
            # MTB alignment and in-compositor tonemapping are only implemented
            # in the Blender 5.0+ merge script
            if merge_py.name == "blender_merge_5.0.py":
                cmd.append("1" if do_mtb_align else "0")
                cmd.append(jpg_path.as_posix())
            cmd += img_list
            run_subprocess_with_prefix(cmd, i, "blender", out_folder)

            # Delete .blend1 backup file created by Blender
            blend1_path = exr_path.with_name("bracket_%03d_sample.blend1" % i)
            if blend1_path.exists():
                blend1_path.unlink()

        if not jpg_path.exists():
            cmd = [
                luminance_cli_exe,
                "-l",
                exr_path.as_posix(),
                "--tmo",
                "reinhard05",
                "-g",
                "2.2",
                "-b",
                "-q",
                "98",
                "-o",
                jpg_path.as_posix(),
            ]
            run_subprocess_with_prefix(cmd, i, "luminance", out_folder)
            if VERBOSE:
                print(
                    "Folder %s: Bracket %d: Complete %s"
                    % (folder.name, i, [pathlib.Path(p.split("___")[0]).name for p in img_list])
                )
            else:
                print("Folder %s: Bracket %d: Complete" % (folder.name, i))

        self.completed_sets_global += 1
        self._update_progress()

    def process_folder(
        self,
        folder: pathlib.Path,
        blender_exe: str,
        luminance_cli_exe: str,
        align_image_stack_exe: str,
        merge_blend: pathlib.Path,
        merge_py: pathlib.Path,
        original_extension: str,
        do_align: bool,
        do_mtb_align: bool,
        do_raw: bool,
        rawtherapee_cli_exe: str,
        pp3_file: str,
        executor: ThreadPoolExecutor,
        output_format: str = "exr",
        brackets_override: int = None,
    ) -> tuple:
        """
        Process a single folder and return (num_brackets, num_sets, threads, error).

        Args:
            brackets_override: If set, use this as the number of images per bracket
                instead of auto-detecting it from EXIF data.

        Returns:
            tuple: (brackets, sets, threads, error_message)
        """
        out_folder = folder / "Merged"

        # If RAW processing is enabled, process RAW files first
        if do_raw and pp3_file and pathlib.Path(pp3_file).exists():
            tif_folder = self.process_raw_with_rawtherapee(
                rawtherapee_cli_exe, pp3_file, folder, original_extension, executor
            )
            if tif_folder:
                folder = tif_folder
                extension = ".tif"
            else:
                return (0, 0, [], "RAW processing failed")
        else:
            extension = original_extension

        glob = extension
        if "*" not in glob:
            glob = "*%s" % glob
        files = list(folder.glob(glob))

        if not files:
            return (0, 0, [], "No matching files found")

        # Analyze EXIF to determine number of brackets, unless manually overridden
        if brackets_override:
            exifs = [get_exif(f) for f in files[:brackets_override]]
            brackets = brackets_override
        else:
            exifs = []
            for f in files:
                e = get_exif(f)
                if e in exifs:
                    break
                exifs.append(e)
            brackets = len(exifs)
        print("\nFolder: %s" % folder)
        print("Brackets:", brackets)
        sets = chunks(files, brackets)
        incomplete_sets = [s for s in sets if len(s) != brackets]
        if incomplete_sets:
            sets = [s for s in sets if len(s) == brackets]
            print(
                "Folder %s: Skipping %d incomplete set(s) (expected %d images per bracket)"
                % (folder.name, len(incomplete_sets), brackets)
            )
        print("Sets:", len(sets), "\n")
        if VERBOSE:
            print("Exifs:\n", str(exifs).replace("}, {", "},\n{"))
        evs = [
            ev_diff(
                {"shutter_speed": 1000000000, "aperture": 0.1, "iso": 1000000000000}, e
            )
            for e in exifs
        ]
        evs = [ev - min(evs) for ev in evs]

        filter_used = "None"

        # Submit merging tasks to the shared executor
        threads = []
        for i, s in enumerate(sets):
            img_list = []
            for ii, img in enumerate(s):
                img_list.append(img.as_posix() + "___" + str(evs[ii]))

            t = executor.submit(
                self.do_merge,
                blender_exe,
                merge_blend,
                merge_py,
                exifs,
                out_folder,
                filter_used,
                i,
                img_list,
                folder,
                luminance_cli_exe,
                align_image_stack_exe,
                do_align,
                do_mtb_align,
                output_format,
            )
            threads.append((i, t))

        return (brackets, len(sets), threads, None)

    def set_progress_totals(self, total_sets: int):
        """Set the total number of sets for progress tracking."""
        self.total_sets_global = total_sets
        self.completed_sets_global = 0

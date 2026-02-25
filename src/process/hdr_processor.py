"""
HDR Processor Module

Contains core processing logic for HDR image merging:
- process_raw_with_rawtherapee: Process RAW files using RawTherapee CLI
- do_merge: Merge bracketed images into HDR using Blender
- process_folder: Process a single folder of images
"""

import pathlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import cv2

from constants import VERBOSE
from process.run_subprocess_with_prefix import run_subprocess_with_prefix
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

    def _align_with_opencv(
        self, img_paths, align_folder, bracket_index, folder, out_folder
    ):
        """
        Align images using OpenCV's AlignMTB algorithm.

        Args:
            img_paths: List of image paths (with ___EV suffix)
            align_folder: Output folder for aligned images
            bracket_index: Bracket set index
            folder: Parent folder for logging
            out_folder: Output folder for saving logs

        Returns:
            List of aligned image paths (with ___EV suffix)
        """
        # Create log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = "bracket_%03d_mergeMTB_%s.log" % (bracket_index, timestamp)
        log_path = out_folder / "logs" / log_filename
        log_path.parent.mkdir(parents=True, exist_ok=True)

        log_messages = []
        log_messages.append(
            "Folder %s: Bracket %d: Aligning images with OpenCV AlignMTB"
            % (folder.name, bracket_index)
        )

        # Extract actual image paths (remove ___EV suffix)
        actual_img_paths = [p.split("___")[0] for p in img_paths]
        ev_values = [p.split("___")[1] for p in img_paths]

        log_messages.append("Loading %d images for alignment" % len(actual_img_paths))

        # Load all images
        images = []
        for img_path in actual_img_paths:
            img = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if img is None:
                error_msg = "Folder %s: Failed to load image %s" % (
                    folder.name,
                    img_path,
                )
                log_messages.append(error_msg)
                # Write log file
                with open(log_path.as_posix(), "w") as log_file:
                    log_file.write("STDOUT:\n")
                    log_file.write("\n".join(log_messages))
                    log_file.write("\nSTDERR:\n")
                    log_file.write(error_msg)
                raise Exception(error_msg)
            images.append(img)

        log_messages.append("Images loaded successfully")

        # Initialize AlignMTB and align images
        log_messages.append("Initializing AlignMTB")
        alignMTB = cv2.createAlignMTB()

        log_messages.append("Running AlignMTB.process()")
        try:
            alignMTB.process(images, images)
            log_messages.append("Alignment completed successfully")
        except Exception as e:
            error_msg = "Folder %s: Bracket %d: OpenCV alignment error: %s" % (
                folder.name,
                bracket_index,
                e,
            )
            log_messages.append(error_msg)
            # Write log file
            with open(log_path.as_posix(), "w") as log_file:
                log_file.write("STDOUT:\n")
                log_file.write("\n".join(log_messages))
                log_file.write("\nSTDERR:\n")
                log_file.write(error_msg)
            raise

        # Save aligned images
        aligned_paths = []

        for j, aligned_img in enumerate(images):
            # Create output filename
            output_filename = "align_{}_{}.tif".format(bracket_index, str(j).zfill(4))
            output_path = align_folder / output_filename

            log_messages.append("Saving aligned image: %s" % output_filename)
            cv2.imwrite(output_path.as_posix(), aligned_img)

            # Add back the EV suffix
            aligned_paths.append(output_path.as_posix() + "___" + ev_values[j])

        log_messages.append(
            "Folder %s: Bracket %d: OpenCV alignment complete, %d images aligned"
            % (folder.name, bracket_index, len(aligned_paths))
        )

        # Write log file
        with open(log_path.as_posix(), "w") as log_file:
            log_file.write("STDOUT:\n")
            log_file.write("\n".join(log_messages))
            log_file.write("\nSTDERR:\n")
            log_file.write("")

        if VERBOSE:
            for msg in log_messages:
                self._log(msg)

        return aligned_paths

    def process_raw_with_rawtherapee(
        self,
        rawtherapee_cli_exe: str,
        pp3_file: str,
        folder: pathlib.Path,
        extension: str,
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

        # Build RawTherapee CLI command
        cmd = [
            rawtherapee_cli_exe,
            "-p",
            pp3_file,
            "-o",
            str(tif_folder),
            "-t",
            "-c",
        ]

        # Add all RAW files to process
        for raw_file in raw_files:
            cmd.append(str(raw_file))

        self._log(
            "Folder %s: Running RawTherapee CLI on %d RAW files..."
            % (folder.name, len(raw_files))
        )
        if VERBOSE:
            self._log("Folder %s: Command: %s" % (folder.name, " ".join(cmd)))

        # Run RawTherapee CLI
        try:
            run_subprocess_with_prefix(cmd, 0, "rawtherapee", out_folder=tif_folder)
        except Exception as ex:
            self._log("Folder %s: Failed to process RAW files: %s" % (folder.name, ex))
            raise

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
        use_opencv: bool = False,
    ):
        """Merge a bracket set into an HDR image."""
        exr_folder = out_folder / "exr"
        jpg_folder = out_folder / "jpg"
        align_folder = out_folder / "aligned"

        exr_folder.mkdir(parents=True, exist_ok=True)
        jpg_folder.mkdir(parents=True, exist_ok=True)

        exr_path = exr_folder / ("merged_%03d.exr" % i)
        jpg_path = jpg_folder / exr_path.with_suffix(".jpg").name

        if exr_path.exists():
            print(
                "Folder %s: Bracket %d: Skipping, %s exists"
                % (folder.name, i, exr_path.relative_to(folder))
            )
            self.completed_sets_global += 1
            self._update_progress()
            return

        if do_align:
            if VERBOSE:
                print(
                    "Folder %s: Bracket %d: Aligning images %s"
                    % (
                        folder.name,
                        i,
                        [pathlib.Path(p.split("___")[0]).name for p in img_list],
                    )
                )
            else:
                print("Folder %s: Bracket %d: Aligning images" % (folder.name, i))

            align_folder.mkdir(parents=True, exist_ok=True)

            if use_opencv:
                # Use OpenCV AlignMTB for alignment
                img_list = self._align_with_opencv(
                    img_list, align_folder, i, folder, out_folder
                )
            else:
                # Use Hugin's align_image_stack for alignment
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
                % (
                    folder.name,
                    i,
                    [pathlib.Path(p.split("___")[0]).name for p in img_list],
                )
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
        cmd += img_list
        run_subprocess_with_prefix(cmd, i, "blender", out_folder)

        # Delete .blend1 backup file created by Blender
        blend1_path = exr_path.with_name("bracket_%03d_sample.blend1" % i)
        if blend1_path.exists():
            blend1_path.unlink()

        cmd = [
            luminance_cli_exe,
            "-l",
            exr_path.as_posix(),
            "--tmo",
            "reinhard02",
            "-q",
            "98",
            "-o",
            jpg_path.as_posix(),
        ]
        run_subprocess_with_prefix(cmd, i, "luminance", out_folder)
        if VERBOSE:
            print(
                "Folder %s: Bracket %d: Complete %s"
                % (
                    folder.name,
                    i,
                    [pathlib.Path(p.split("___")[0]).name for p in img_list],
                )
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
        do_raw: bool,
        rawtherapee_cli_exe: str,
        pp3_file: str,
        executor: ThreadPoolExecutor,
        use_opencv: bool = False,
    ) -> tuple:
        """
        Process a single folder and return (num_brackets, num_sets, threads, error).

        Returns:
            tuple: (brackets, sets, threads, error_message)
        """
        out_folder = folder / "Merged"

        # If RAW processing is enabled, process RAW files first
        if do_raw and pp3_file and pathlib.Path(pp3_file).exists():
            tif_folder = self.process_raw_with_rawtherapee(
                rawtherapee_cli_exe, pp3_file, folder, original_extension
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

        # Analyze EXIF to determine number of brackets
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
                use_opencv,
            )
            threads.append((i, t))

        return (brackets, len(sets), threads, None)

    def cleanup_folder(self, folder: pathlib.Path, was_raw: bool):
        """
        Clean up temporary files after processing.

        Args:
            folder: The original folder that was processed
            was_raw: Whether RAW processing was used (to clean up tif folder)
        """
        self._log("Folder %s: Cleaning up temporary files..." % folder.name)

        # Clean up aligned folder (inside Merged/output folder)
        merged_folder = folder / "Merged"
        aligned_folder = merged_folder / "aligned"
        if aligned_folder.exists():
            try:
                import shutil

                shutil.rmtree(aligned_folder)
                self._log("Folder %s: Deleted aligned folder" % folder.name)
            except Exception as e:
                self._log(
                    "Folder %s: Failed to delete aligned folder: %s" % (folder.name, e)
                )

        # Clean up tif folder (only if RAW processing was used)
        if was_raw:
            tif_folder = folder / "tif"
            if tif_folder.exists():
                try:
                    import shutil

                    shutil.rmtree(tif_folder)
                    self._log("Folder %s: Deleted tif folder" % folder.name)
                except Exception as e:
                    self._log(
                        "Folder %s: Failed to delete tif folder: %s" % (folder.name, e)
                    )

        self._log("Folder %s: Cleanup complete" % folder.name)

    def set_progress_totals(self, total_sets: int):
        """Set the total number of sets for progress tracking."""
        self.total_sets_global = total_sets
        self.completed_sets_global = 0

## Small changes:
- [x] Auto-paste is sometimes annoying, replace this with a Ctrl-V hotkey
- [x] Use existing .pp3 files next to raw files if available
- [x] Perform tonemapping inside Blender instead of Luminance HDR and output JPGs alongside EXRs with a File Output node (inputs already in memory, Blender has arguably better tonemapping capability)
- [x] Include `align_image_stack.exe` in our source - it's GPL too.
- [ ] Define range of valid Blender versions, show warning if invalid
- [ ] Better error handling in general, too many bug reports of people saying "it doesn't work" even when the issue is simple
- [ ] Allow for inconsistant exposure brackets - currently the first exposure set determines how many images there are per set, but it should be possible to support exposure sets with varying numbers of images.

## Big changes:
- [ ] UI overhaul...
  - [ ] Indicate progress per folder
  - [ ] Pause and resume processing
  - [ ] Drag and drop reordering
  - [ ] Thumbnail previews? Could group brackets visually, display progress, and show errors. Would need to be highly performant even over network drive.
- [ ] Replace Blender merging with custom solution that includes deghosting & weighted merging to reduce noise. Possibly built with [OpenCV](https://learnopencv.com/high-dynamic-range-hdr-imaging-using-opencv-cpp-python)
- [ ] Either expose options for align_image_stack.exe, or replace with [OpenCV implementation](https://github.com/khufkens/align_images/blob/master/align_images.py)

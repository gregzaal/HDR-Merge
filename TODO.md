## Small changes:

- [x] Dialog to select exe files for required programs
- added default file paths for both windows and linux
- added a setup dialog, complete with download links. This will open on first run, or can be accessed later throught the setup button
- [x] Ask to download required programs (Blender, etc.) on first use
- links and message included in the setup dialog
- do we need to automate downloading the programs?
- [x] Remember last used threads and other values in config.json
- [x] Store exe_paths in config.json
- [x] Queue/batch processing
- [x] Update to latest required programs (Blender, etc.) for performance benefits
 - works on latest Blender LTS version (4.5) as intended  
 - works on the latest align image stack from ptgui as intended  
 - command line arguments updated to work with Luminance 2.6 
 - works with the latest rawtherapee version  
- [ ] Define range of valid Blender versions, show warning if invalid
 - works on latest Blender LTS version (4.5) as intended
- [ ] Better error handling in general, too many bug reports of people saying "it doesn't work" even when the issue is simple
- [x] Added raw file processing with rawtherapee-cli 
- [ ] Allow for inconsistant exposure brackets - currently the first exposure set determines how many images there are per set, but it should be possible to support exposure sets with varying numbers of images.
- [x] Refactor the code and split it into multiple files, the hdr_brackets.py file is getting too long

## Big changes: 
- [ ] Replace Blender merging with custom solution that includes deghosting & weighted merging to reduce noise. Possibly built with [OpenCV](https://learnopencv.com/high-dynamic-range-hdr-imaging-using-opencv-cpp-python)
- [ ] Either expose options for align_image_stack.exe, or replace with [OpenCV implementation](https://github.com/khufkens/align_images/blob/master/align_images.py)

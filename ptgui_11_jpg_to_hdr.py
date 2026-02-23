import os
import sys
from shutil import copyfile
from time import sleep
import json
import collections

f = sys.argv[1]
# f = "F:\PGT\26-02-27 UCD\Library 2\Library_02_o.pts"  # testing
verbose = True

def go(f):
    filename, p_ext = os.path.splitext(os.path.basename(f))
    folder = os.path.dirname(f)

    data_str = ""
    with open(f, 'r') as fr:
        data = json.load(fr, object_pairs_hook=collections.OrderedDict)

    project_key = ""  # Sometimes it's 'project', sometimes it's 'project_v1'?
    for key in data:
        if 'project' in key:
            project_key = key
            break

    data[project_key]["outputcomponents"]["hdrblended"] = True
    data[project_key]["outputcomponents"]["ldrpanorama"] = False
    data[project_key]["hdrsettings"]["enabled"] = True
    data[project_key]["hdrsettings"]["fileformat"] = "exr"
    data[project_key]["hdrsettings"]["hdrmethod"] = "truehdr"
    data[project_key]["hdrsettings"]["exrparams"]["alphamode"] = "noalpha"
    data[project_key]["hdrsettings"]["exrparams"]["bitdepth"] = "float"
    data[project_key]["hdrsettings"]["exrparams"]["compression"] = "PIZ"
    data[project_key]["outputsize"]["mode"] = "fixed"
    data[project_key]["outputsize"]["pixels"] = 2.097152e8

    if verbose:
        print("keys updated")

    base_dir = os.path.dirname(f)
    images = data[project_key]["imagegroups"]
    for i in images:
        fp = i["images"][0]["filename"]
        formats_to_try = ['exr', 'hdr']
        for i_ext in formats_to_try:
            new_fp = fp.replace("\\jpg\\", "\\"+i_ext+"\\")
            new_fp = new_fp.replace(".jpg", "."+i_ext)
            real_fp = os.path.join(base_dir, new_fp)
            if os.path.exists(real_fp):
                break
        if verbose:
            print("file path updated: ", fp, "->", new_fp)
        fp = new_fp
        i["images"][0]["filename"] = fp
        i["images"][0]["metadata"]["pixelformat"]["datatype"] = "f32"

    f_old = os.path.join(folder, filename+"_t"+p_ext)

    os.rename(f, f_old)
    if verbose:
        print("files paths updated")

    with open(f, 'w') as fw:
        # json.dump(data, fw) # old formatting method with no indents, smallest file size, basically unreadable
        # json.dump(data, fw, indent=4) # old formatting method with four spaces used as indents, results in double the file size
        json.dump(data, fw, indent='\t', separators=(',', ':')) # new formatting method with tab used as indent, results in 1.5 file size


go(f)
sleep(1)
ptgui_path = "C:\\Program Files\\PTGui\\PTGui.exe"
if os.path.exists(ptgui_path):
    cmd = "start \"" + ptgui_path + "\" " + '"' + f + '"'
    print(cmd)
    os.system(cmd)
print("Done")
sleep(2)
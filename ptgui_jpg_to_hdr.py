import os
import sys
from shutil import copyfile
from time import sleep
import json
import collections

f = sys.argv[1]
# f = "X:\\Panos\\misty_dawn\\misty_dawn.pts"  # testing


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
    data[project_key]["hdrsettings"]["fileformat"] = "hdr"
    data[project_key]["hdrsettings"]["hdrmethod"] = "truehdr"
    data[project_key]["hdrsettings"]["fileformat"] = "exr"
    data[project_key]["hdrsettings"]["precision"] = "float"
    data[project_key]["hdrsettings"]["exrparams"]["alphamode"] = "noalpha"
    data[project_key]["hdrsettings"]["exrparams"]["bitdepth"] = "float"
    data[project_key]["hdrsettings"]["exrparams"]["compression"] = "PIZ"

    for ig in data[project_key]["imagegroups"]:
        for im in ig["images"]:
            im["photometric"]["globalcameracurve"] = None

    for gcc in data[project_key]["globalcameracurves"]:
        gcc["toning"]["luminancecurve"]["a"] = 0
        gcc["toning"]["luminancecurve"]["b"] = 0

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
        fp = new_fp
        i["images"][0]["filename"] = fp
        i["images"][0]["metadata"]["pixelformat"]["datatype"] = "f32"

    f_old = os.path.join(folder, filename+"__t"+p_ext)
    os.rename(f, f_old)

    with open(f, 'w') as fw:
        # Add indent=4 for pretty formatting, but double file size
        json.dump(data, fw)


go(f)
sleep(1)
ptgui_path = "C:\\Program Files\\PTGui\\PTGui.exe"
if os.path.exists(ptgui_path):
    cmd = "start \"" + ptgui_path + "\" " + '"' + f + '"'
    print(cmd)
    os.system(cmd)
print("Done")
sleep(1)

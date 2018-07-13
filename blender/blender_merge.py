import bpy
import os
import sys

# Example call:
# blender.exe --background HDR_Merge.blend --factory-startup --python blender_merge.py -- 3456x5184 "C:/foo/bar/Merged" ND8_ND400 0 imgpath1___12 imgpath2___9 imgpath3___6 imgpath4___3 imgpath5___0

argv = sys.argv
argv = argv[argv.index("--")+1:]  # get all args after "--"
RESOLUTION = [int(d) for d in argv[0].split('x')]  # list where first position is X-res, second position is Y-res
OUT_FOLDER = argv[1]
FILTERS = argv[2]
INDEX = int(argv[3])  # Current set number
IMAGES = sorted([i.split("___") for i in argv[4:]], key=lambda x: float(x[1]))

nodes = []
groups = [None]
nt = bpy.context.scene.node_tree
for i, (img_path, ev) in enumerate(IMAGES):
    ev = float(ev)
    nodes.append(nt.nodes.new("CompositorNodeImage"))
    print ("Loading:", os.path.basename(img_path))
    img = bpy.data.images.load(img_path)
    nodes[i].image = img
    if i != 0:
        groups.append(nt.nodes.new("CompositorNodeGroup"))
        groups[i].node_tree = bpy.data.node_groups['Merge HDR']
        nt.links.new(nodes[i-1].outputs[0], groups[i].inputs[0])
        nt.links.new(nodes[i].outputs[0], groups[i].inputs[1])
        if i == 1:
            nt.links.new(nodes[i-1].outputs[0], groups[i].inputs[2])
        else:
            nt.links.new(groups[i-1].outputs[0], groups[i].inputs[2])
        groups[i].inputs[3].default_value = ev

nt.links.new(groups[-1].outputs[0], nt.nodes['OUT'].inputs[0])

# Filters
def filter_fix(filter_type, node_tree, img_nodes):
    for n in img_nodes:
        links = n.outputs[0].links
        g = node_tree.nodes.new("CompositorNodeGroup")
        g.node_tree = bpy.data.node_groups[filter_type]
        node_tree.links.new(n.outputs[0], g.inputs[0])
        for l in links:
            node_tree.links.new(g.outputs[0], l.to_socket)
if "ND8" in FILTERS:
    filter_fix('ND8', nt, nodes)
if "ND400" in FILTERS:
    filter_fix('ND400', nt, nodes)

OUT_FOLDER = OUT_FOLDER.replace('\\', '/')
OUT_FOLDER += '/' if not OUT_FOLDER.endswith('/') else ''
if not os.path.exists(OUT_FOLDER):
    os.makedirs(OUT_FOLDER)

rset = bpy.context.scene.render
rset.filepath = OUT_FOLDER + "merged_" + str(INDEX).zfill(3) + ".exr"
rset.resolution_x = RESOLUTION[0]
rset.resolution_y = RESOLUTION[1]

bpy.ops.render.render(write_still=True)  # Render!

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT_FOLDER, "bracket_sample.blend"))

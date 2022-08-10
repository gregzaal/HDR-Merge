import bpy
import os
import pathlib
import sys

# Example call:
# blender.exe --background HDR_Merge.blend --factory-startup --python blender_merge.py -- 3456x5184 "C:/foo/bar/Merged/exr/merged_000.exr" ND8_ND400 imgpath1___12 imgpath2___9 imgpath3___6 imgpath4___3 imgpath5___0

argv = sys.argv
argv = argv[argv.index("--")+1:]  # get all args after "--"
# list where first position is X-res, second position is Y-res
RESOLUTION = [int(d) for d in argv[0].split('x')]
EXR_OUTFILE = argv[1]
FILTERS = argv[2]
IMAGES = sorted([i.split("___") for i in argv[3:]], key=lambda x: float(x[1]))

exr_fpath = pathlib.Path(EXR_OUTFILE)

nodes = []
previous_node = None
previous_group = None
groups = [None]
nt = bpy.context.scene.node_tree
for i, (img_path, ev) in enumerate(IMAGES):
    ev = float(ev)
    n = nt.nodes.new("CompositorNodeImage")
    nodes.append(n)
    print("Loading:", i, os.path.basename(img_path))
    img = bpy.data.images.load(img_path)
    n.image = img
    if i != 0:
        print("Creating group", i)
        g = nt.nodes.new("CompositorNodeGroup")
        groups.append(g)
        g.node_tree = bpy.data.node_groups['Merge HDR']
        nt.links.new(previous_node.outputs[0], g.inputs[0])
        nt.links.new(n.outputs[0], g.inputs[1])
        if i == 1:
            nt.links.new(previous_node.outputs[0], g.inputs[2])
        else:
            nt.links.new(previous_group.outputs[0], g.inputs[2])
        g.inputs[3].default_value = ev
        previous_group = g
    previous_node = n

bpy.ops.wm.save_as_mainfile(
    filepath=str(exr_fpath.with_name("bracket_sample.blend")),
    compress=True,
)

nt.links.new(groups[-1].outputs[0], nt.nodes['OUT'].inputs[0])


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

if not exr_fpath.parent.exists():
    exr_fpath.parent.mkdir(parents=True, exist_ok=True)

rset = bpy.context.scene.render
rset.filepath = str(exr_fpath)
rset.resolution_x = RESOLUTION[0]
rset.resolution_y = RESOLUTION[1]

bpy.ops.render.render(write_still=True)  # Render!

bpy.ops.wm.save_as_mainfile(
    filepath=str(exr_fpath.with_name("bracket_sample.blend")),
    compress=True,
)

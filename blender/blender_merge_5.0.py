import sys
import os
import pathlib

# Example call:
# blender.exe --background HDR_Merge.blend --factory-startup --python blender_merge.py -- 3456x5184 "C:/foo/bar/Merged/exr/merged_000.exr" ND8_ND400 0 1 imgpath1___12 imgpath2___9 imgpath3___6 imgpath4___3 imgpath5___0

argv = sys.argv
argv = argv[argv.index("--") + 1 :]  # get all args after "--"
RESOLUTION = [int(d) for d in argv[0].split("x")]
EXR_OUTFILE = argv[1]
FILTERS = argv[2]
BRACKET_ID = int(argv[3])  # Bracket ID for unique filenames
DO_MTB_ALIGN = argv[4] == "1"  # Whether to calculate MTB pixel-shift alignment
IMAGES = sorted([i.split("___") for i in argv[5:]], key=lambda x: float(x[1]))

exr_fpath = pathlib.Path(EXR_OUTFILE)

# -----------------------------------------------------------------------------
# 1. MTB Shift Calculation using OpenCV (skipped if DO_MTB_ALIGN is False)
# -----------------------------------------------------------------------------
if DO_MTB_ALIGN:
    import subprocess
    import site

    # Try importing cv2; if missing, install it directly inside Blender
    try:
        import cv2
    except ImportError:
        print("Installing opencv-python into Blender environment...")
        subprocess.call([sys.executable, "-m", "pip", "install", "opencv-python", "--user"])

        # Reload site-packages path so Python detects the newly installed module
        user_site = site.getusersitepackages()
        if user_site not in sys.path:
            sys.path.append(user_site)

        import cv2

    print("Calculating MTB pixel shifts...")
    image_paths = [img_path for img_path, _ in IMAGES]
    cv_images = [cv2.imread(p) for p in image_paths]

    # Pick middle exposure as reference
    ref_idx = len(cv_images) // 2

    # Convert reference image to Grayscale (single channel required for calculateShift)
    ref_gray = cv2.cvtColor(cv_images[ref_idx], cv2.COLOR_BGR2GRAY)

    align_mtb = cv2.createAlignMTB(max_bits=4, exclude_range=4, cut=True)
    mtb_shifts = []

    for idx, cv_img in enumerate(cv_images):
        # Convert current frame to Grayscale
        img_gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

        # Calculate shift on grayscale images
        shift = align_mtb.calculateShift(ref_gray, img_gray)
        mtb_shifts.append(shift)
        print(f"  Image {idx}: {os.path.basename(image_paths[idx])} -> Shift (X, Y): {shift}")
else:
    print("Skipping MTB alignment - inserting identity Translate nodes for manual adjustment.")
    mtb_shifts = [(0.0, 0.0) for _ in IMAGES]

import bpy

# -----------------------------------------------------------------------------
# 2. Blender Compositor Node Tree Setup
# -----------------------------------------------------------------------------
# Node layout constants - purely cosmetic, arranges the generated nodes into a
# readable grid instead of stacking them all on top of each other at (0, 0).
# Rows flow top-to-bottom by node type (Image -> Translate -> Merge), columns
# flow left-to-right, one column per bracketed image.
NODE_SPACING_X = 300
NODE_SPACING_Y = 300
IMAGE_ROW_Y = 0
TRANSLATE_ROW_Y = -NODE_SPACING_Y
MERGE_ROW_Y = -NODE_SPACING_Y * 2

nodes = []
previous_node = None
previous_group = None
groups = [None]
nt = bpy.context.scene.compositing_node_group

for i, (img_path, ev) in enumerate(IMAGES):
    ev = float(ev)
    col_x = i * NODE_SPACING_X
    n = nt.nodes.new("CompositorNodeImage")
    n.location = (col_x, IMAGE_ROW_Y)
    print("Loading:", i, os.path.basename(img_path))
    img = bpy.data.images.load(img_path)
    n.image = img

    # --- Insert Translate Node for MTB Shift ---
    shift_x, shift_y = mtb_shifts[i]
    t_node = nt.nodes.new("CompositorNodeTranslate")
    t_node.location = (col_x, TRANSLATE_ROW_Y)

    # Handle API differences between Blender 5.0+ and earlier versions
    if hasattr(t_node, "mode"):
        t_node.mode = 'ABSOLUTE'
    elif hasattr(t_node, "use_relative"):
        t_node.use_relative = False

    t_node.inputs["X"].default_value = float(shift_x)
    t_node.inputs["Y"].default_value = float(shift_y)

    nt.links.new(n.outputs[0], t_node.inputs[0])

    # Record the translate node as the output source for subsequent nodes
    active_output_node = t_node
    nodes.append(active_output_node)

    # --- HDR Merge Node Setup ---
    if i != 0:
        print("Creating group", i)
        g = nt.nodes.new("CompositorNodeGroup")
        # Same column as the translate node it's folding in, one row down.
        g.location = (col_x, MERGE_ROW_Y)
        groups.append(g)
        g.node_tree = bpy.data.node_groups["Merge HDR"]
        nt.links.new(previous_node.outputs[0], g.inputs[0])
        nt.links.new(active_output_node.outputs[0], g.inputs[1])
        if i == 1:
            nt.links.new(previous_node.outputs[0], g.inputs[2])
        else:
            nt.links.new(previous_group.outputs[0], g.inputs[2])
        g.inputs[3].default_value = ev
        previous_group = g

    previous_node = active_output_node

bpy.ops.wm.save_as_mainfile(
    filepath=str(exr_fpath.with_name("bracket_%03d_sample.blend" % BRACKET_ID)),
    compress=True,
)

nt.links.new(groups[-1].outputs[0], nt.nodes["OUT"].inputs[0])
# Place the output node one column past the final merge group, same row.
nt.nodes["OUT"].location = (groups[-1].location.x + NODE_SPACING_X, MERGE_ROW_Y)


def filter_fix(filter_type, node_tree, img_nodes):
    for n in img_nodes:
        links = n.outputs[0].links
        g = node_tree.nodes.new("CompositorNodeGroup")
        g.node_tree = bpy.data.node_groups[filter_type]
        # Sit the filter halfway between the row it taps and the row it feeds.
        g.location = (n.location.x, n.location.y - NODE_SPACING_Y * 0.5)
        node_tree.links.new(n.outputs[0], g.inputs[0])
        for l in links:
            node_tree.links.new(g.outputs[0], l.to_socket)


if "ND8" in FILTERS:
    filter_fix("ND8", nt, nodes)
if "ND400" in FILTERS:
    filter_fix("ND400", nt, nodes)

if not exr_fpath.parent.exists():
    exr_fpath.parent.mkdir(parents=True, exist_ok=True)

rset = bpy.context.scene.render
rset.filepath = str(exr_fpath)
rset.resolution_x = RESOLUTION[0]
rset.resolution_y = RESOLUTION[1]

bpy.ops.render.render(write_still=True)  # Render!

bpy.ops.wm.save_as_mainfile(
    filepath=str(exr_fpath.with_name("bracket_%03d_sample.blend" % BRACKET_ID)),
    compress=True,
)
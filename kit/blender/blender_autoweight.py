"""Optional Mode C: automatic bone weights in the user's local Blender, exported as .glb.

  python blender_autoweight.py --check                    # is Blender here? (exit 0 yes, 2 no)
  blender -b -P blender_autoweight.py -- in.blend out.glb # parent every mesh to the armature with automatic weights

Only when the user chose a real deforming model AND Blender is installed; otherwise use Mode B (guide "3d").
After rigging it reports meshes with vertices no bone moves, and prints the Weight Paint fix-up checklist if any.
"""
import shutil, subprocess, sys

FIX = """Weights need a hand (Blender, 2 minutes):
1. Select the mesh -> Weight Paint mode.
2. Pick the bone that misbehaves; paint its weight off the wrong area (Subtract brush),
   or Weights -> Assign Automatic from Bones for that bone only.
3. Object Data -> Vertex Groups: delete empty or misnamed groups.
4. Save, and tell Claude to export again."""


def check():
    exe = shutil.which("blender")
    if not exe:
        print("Blender not found on PATH: use Mode B (skeletonless) instead.")
        return 2
    print(subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.splitlines()[0])
    return 0


def rig(src, dst):
    import bpy
    bpy.ops.wm.open_mainfile(filepath=src)
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if arm is None:
        sys.exit("no armature in the file")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    for m in meshes:
        bpy.ops.object.select_all(action="DESELECT")
        m.select_set(True); arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")     # = weight_from_bones(type='AUTOMATIC') per mesh
    loose = {m.name: sum(1 for v in m.data.vertices if sum(g.weight for g in v.groups) < 1e-4) for m in meshes}
    loose = {k: n for k, n in loose.items() if n}
    bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB")
    print(f"exported {dst}")
    if loose:
        print("vertices no bone moves:", loose)
        print(FIX)


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    if "--" not in sys.argv:
        sys.exit(__doc__)
    rig(*sys.argv[sys.argv.index("--") + 1:][:2])

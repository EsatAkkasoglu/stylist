"""Blender as a modelling tool only: build props with a bpy script, export geometry (no rendering) for a code renderer.

  python mesh_export.py --check                       # find Blender (PATH, STYLIST_BLENDER, Program Files, Steam libraries)
  python mesh_export.py --run model.py out.json       # run a bpy model script headless; it ends with export(out)

In a model script (runs inside Blender):
  import sys; sys.path.append(KIT_BLENDER_DIR); from mesh_export import export, part
  ... build objects; part(obj, "turret", "#7C8A4E") tags an object with its part name and flat colour ...
  export(sys.argv[-1])

out.json: {"parts": [{"name", "color", "verts": [[x,y,z]...], "faces": [[i,j,k,...]...], "normals": [[x,y,z]...]}]}
Coordinates are converted to Y-up centimetres (Blender Z-up metres): (x, z, -y) * 100. Modifiers are applied.
"""
import glob, json, os, re, shutil, subprocess, sys
from pathlib import Path


def find_blender():
    c = os.environ.get("STYLIST_BLENDER") or shutil.which("blender")
    if c: return c
    pats = ["C:/Program Files/Blender Foundation/*/blender.exe", "/Applications/Blender.app/Contents/MacOS/Blender",
            "/usr/bin/blender", "/snap/bin/blender"]
    libs = ["C:/Program Files (x86)/Steam", "C:/Program Files/Steam", os.path.expanduser("~/.steam/steam")]
    for lib in list(libs):                                    # Steam keeps extra library folders in libraryfolders.vdf
        vdf = Path(lib) / "steamapps" / "libraryfolders.vdf"
        if vdf.exists(): libs += [p.replace("\\\\", "/") for p in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(errors="ignore"))]
    for d in "CDEFG": libs.append(f"{d}:/SteamLibrary")
    pats += [f"{l}/steamapps/common/Blender/blender{'.exe' if os.name == 'nt' else ''}" for l in libs]
    for p in pats:
        hit = sorted(glob.glob(p))
        if hit: return hit[-1]
    return None


# ------------------------------------------------------------------ inside Blender
def part(obj, name, color):
    obj["part"] = name; obj["color"] = color
    return obj


def export(path, scale=100.0):
    import bpy
    dg = bpy.context.evaluated_depsgraph_get(); parts = []
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or ob.hide_render: continue
        ev = ob.evaluated_get(dg); me = ev.to_mesh(); M = ob.matrix_world; R = M.to_3x3().inverted().transposed()
        conv = lambda v: [round(v.x * scale, 4), round(v.z * scale, 4), round(-v.y * scale, 4)]
        verts = [conv(M @ v.co) for v in me.vertices]
        normals = []
        for p in me.polygons:
            n = (R @ p.normal).normalized(); normals.append([round(n.x, 5), round(n.z, 5), round(-n.y, 5)])
        parts.append({"name": ob.get("part", ob.name), "color": ob.get("color", "#C9CDD2"), "verts": verts,
                      "faces": [list(p.vertices) for p in me.polygons], "normals": normals})
        ev.to_mesh_clear()
    Path(path).write_text(json.dumps({"parts": parts}), "utf8")
    print(f"exported {len(parts)} parts, {sum(len(p['faces']) for p in parts)} faces -> {path}")


if __name__ == "__main__":
    b = find_blender()
    if "--check" in sys.argv:
        print(b or "Blender not found (set STYLIST_BLENDER)"); sys.exit(0 if b else 2)
    if "--run" in sys.argv:
        i = sys.argv.index("--run"); script, out = sys.argv[i + 1], sys.argv[i + 2]
        if not b: sys.exit("Blender not found (set STYLIST_BLENDER)")
        # clean env: a Python/conda on PATH or PYTHON* variables can hang Blender's bundled Python at start-up (seen on Windows)
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "CONDA"))}
        if os.name == "nt": env["PATH"] = os.path.expandvars(r"%SystemRoot%\system32;%SystemRoot%")
        r = subprocess.run([b, "-b", "--factory-startup", "-P", str(Path(script).resolve()), "--", str(Path(__file__).parent.resolve()), str(Path(out).resolve())],
                           capture_output=True, text=True, env=env, timeout=600)
        print("\n".join(l for l in (r.stdout + r.stderr).splitlines() if "exported" in l or "Error" in l or "Traceback" in l or l.startswith("  File")))
        sys.exit(r.returncode)

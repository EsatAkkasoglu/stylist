"""Measure a rigged character instead of trusting the script that built it: topology, transforms, symmetry, rig and a
joint-bend test, plus a rest/posed turnaround sheet you must open and look at.

  python character_check.py model.blend out_dir         # -> out_dir/check.json, out_dir/sheet.png; exit 0 pass, 1 fail

Checks (each one PASS / WARN / FAIL with numbers):
  topology   cage mesh: n-gons, triangles share, loose and duplicate verts; evaluated mesh: non-manifold edges, flipped faces
  transforms every mesh and armature has location-independent rotation 0 and scale 1 applied
  symmetry   every .L bone has a mirrored .R bone (X within 1 mm); the mesh mirrors onto itself
  rig        Armature modifier with Preserve Volume, before Subdivision; every vertex weighted; no vertex group without a bone;
             IK on the limbs has a pole target
  bend       each deform bone bent 70 deg (IK muted): wrong-side drag (a .L bone moving .R vertices = a leg pulling the
             other leg), pinch (faces shrinking under 25 % of their area), volume kept
The sheet: 4 rest views + 4 posed views (IK targets moved: arms up and forward, one knee raised), Workbench, flat light.
"""
import json, math, os, subprocess, sys
from pathlib import Path


def host(blend, out):
    sys.path.insert(0, str(Path(__file__).parent))
    from mesh_export import run_blender
    Path(out).mkdir(parents=True, exist_ok=True)
    code = run_blender(__file__, blend, out, show=("CHECK", "Error", "Traceback", "  File"))
    views = sorted(Path(out).glob("view_*.png"))
    if views:   # 4x2 contact sheet with ffmpeg (a Stylist requirement anyway)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(Path(out) / "view_%d.png"), "-vf", "tile=4x2", str(Path(out) / "sheet.png")], check=False)
        for v in views: v.unlink()
    rep = json.loads((Path(out) / "check.json").read_text("utf8")) if (Path(out) / "check.json").exists() else None
    if not rep: return 1
    for k, v in rep["checks"].items(): print(f"{v['status']:4}  {k:10} {v['note']}")
    print(f"sheet: {Path(out) / 'sheet.png'}  (open it: rest row on top, posed row below)")
    return 0 if rep["pass"] else 1


# ------------------------------------------------------------------ inside Blender
def inside(blend, out):
    import bpy, bmesh
    from mathutils import Vector, kdtree
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == "MESH" and not o.hide_render]
    arm = next((o for o in sc.objects if o.type == "ARMATURE"), None)
    body = max(meshes, key=lambda o: len(o.data.vertices))
    checks = {}
    def put(name, status, note, **data): checks[name] = {"status": status, "note": note, **data}

    # topology: cage (what the artist edits) and evaluated (what renders)
    me = body.data
    ngons = sum(1 for p in me.polygons if len(p.vertices) > 4)
    tris = sum(1 for p in me.polygons if len(p.vertices) == 3)
    used = {v for p in me.polygons for v in p.vertices}
    loose = len(me.vertices) - len(used)
    kd = kdtree.KDTree(len(me.vertices))
    for v in me.vertices: kd.insert(v.co, v.index)
    kd.balance()
    dup = sum(1 for v in me.vertices if len(kd.find_range(v.co, 1e-5)) > 1) // 2
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new(); bm.from_object(body, dg)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    bad_wind = sum(1 for e in bm.edges if e.is_manifold and not e.is_contiguous)   # neighbours disagree = a flipped face
    vol = bm.calc_volume(signed=True)
    bm.free()
    st = "FAIL" if ngons or nonman or bad_wind or dup or vol < 0 else ("WARN" if tris > 0.02 * len(me.polygons) or loose else "PASS")
    put("topology", st, f"{len(me.polygons)} cage faces, {ngons} n-gons, {tris} tris, {loose} loose, {dup} duplicate verts; "
        f"evaluated: {nonman} non-manifold edges, {bad_wind} flipped-face edges, volume {'inside-out' if vol < 0 else 'ok'}",
        ngons=ngons, tris=tris, nonmanifold=nonman, flipped=bad_wind)

    # transforms
    off = [o.name for o in meshes + ([arm] if arm else []) if (o.scale - Vector((1, 1, 1))).length > 1e-4 or Vector(o.rotation_euler).length > 1e-4]
    put("transforms", "FAIL" if off else "PASS", f"unapplied rotation/scale on {off}" if off else "rotation 0, scale 1 everywhere", objects=off)

    # symmetry: bones by name and position, mesh by mirror lookup (evaluated, rest pose)
    if arm:
        bones = arm.data.bones
        lefts = [b for b in bones if b.name.endswith(".L")]
        miss = [b.name for b in lefts if b.name[:-2] + ".R" not in bones]
        skew = [b.name for b in lefts if b.name[:-2] + ".R" in bones and
                (Vector((-b.head_local.x, b.head_local.y, b.head_local.z)) - bones[b.name[:-2] + ".R"].head_local).length > 1e-3]
        odd = [b.name for b in bones if b.name.lower().endswith(("_l", "_r", ".left", ".right", "left", "right"))]
    else:
        miss, skew, odd, lefts = [], [], [], []
    ev = body.evaluated_get(dg); m2 = ev.to_mesh()
    pts = [body.matrix_world @ v.co for v in m2.vertices]
    kd2 = kdtree.KDTree(len(pts))
    for i, p in enumerate(pts): kd2.insert(p, i)
    kd2.balance()
    mirr = sum(1 for p in pts if kd2.find(Vector((-p.x, p.y, p.z)))[2] < 2e-3) / max(len(pts), 1)
    ev.to_mesh_clear()
    st = "FAIL" if miss or skew or mirr < .98 else ("WARN" if odd else "PASS")
    put("symmetry", st, f"{len(lefts)} .L bones, missing .R {miss}, unmirrored {skew}, non-.L/.R names {odd}; mesh mirrors {mirr:.1%}",
        mesh_mirror=round(mirr, 4))

    # rig
    if not arm:
        put("rig", "FAIL", "no armature")
    else:
        mods = list(body.modifiers)
        am = next((m for m in mods if m.type == "ARMATURE"), None)
        sub = next((i for i, m in enumerate(mods) if m.type == "SUBSURF"), None)
        unw = sum(1 for v in me.vertices if sum(g.weight for g in v.groups if body.vertex_groups[g.group].name in arm.data.bones) < 1e-4)
        orphan = [g.name for g in body.vertex_groups if g.name not in arm.data.bones]
        iks = [(pb.name, c.pole_target is not None) for pb in arm.pose.bones for c in pb.constraints if c.type == "IK"]
        nopole = [n for n, p in iks if not p]
        probs = []
        if not am: probs.append("no Armature modifier")
        elif not am.use_deform_preserve_volume: probs.append("Preserve Volume off")
        if am and sub is not None and mods.index(am) > sub: probs.append("Armature after Subdivision (slow, softer weights)")
        if unw: probs.append(f"{unw} unweighted verts")
        if nopole: probs.append(f"IK without pole: {nopole}")
        put("rig", "FAIL" if probs and (not am or unw or nopole) else ("WARN" if probs or orphan else "PASS"),
            "; ".join(probs) or f"{len(arm.data.bones)} bones, {len(iks)} IK chains with poles, all verts weighted"
            + (f"; groups without a bone: {orphan}" if orphan else ""), ik=len(iks), unweighted=unw)

    # bend test: IK muted, each deform bone with a parent bent 70 deg about its local X
    def snap():
        e = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); m = e.to_mesh()
        v = [body.matrix_world @ x.co for x in m.vertices]
        a = [p.area for p in m.polygons]; f = [tuple(p.vertices) for p in m.polygons]
        bm = bmesh.new(); bm.from_mesh(m); vol = abs(bm.calc_volume()); bm.free(); e.to_mesh_clear()
        return v, a, f, vol
    if arm:
        cons = [c for pb in arm.pose.bones for c in pb.constraints]
        for c in cons: c.mute = True
        subs = [m for m in body.modifiers if m.type == "SUBSURF" and m.show_viewport]
        for m in subs: m.show_viewport = False     # measure the weights on the cage; Subdivision only smooths them
        bpy.context.view_layer.update()
        v0, a0, f0, vol0 = snap()
        worst, rows = {"drag": 0, "pinch": 0, "vol": 1.0}, []
        for pb in arm.pose.bones:
            b = pb.bone
            if not b.use_deform or not b.parent: continue
            pb.rotation_mode = "XYZ"; pb.rotation_euler = (math.radians(70), 0, 0)
            bpy.context.view_layer.update()
            v1, a1, _, vol1 = snap()
            side = 1 if b.name.endswith(".L") else -1 if b.name.endswith(".R") else 0
            drag = sum(1 for p, q in zip(v0, v1) if side and p.x * side < -0.02 and (p - q).length > 1e-3) if len(v0) == len(v1) else 0
            moved = [i for i, f in enumerate(f0) if len(a1) == len(a0) and any((v0[k] - v1[k]).length > 1e-3 for k in f)]
            pinch = sum(1 for i in moved if a0[i] > 1e-9 and a1[i] / a0[i] < .25)
            rows.append({"bone": b.name, "drag": drag, "pinch": pinch, "volume": round(vol1 / max(vol0, 1e-9), 3)})
            worst = {"drag": max(worst["drag"], drag), "pinch": max(worst["pinch"], pinch), "vol": min(worst["vol"], vol1 / max(vol0, 1e-9))}
            pb.rotation_euler = (0, 0, 0)
        for c in cons: c.mute = False
        for m in subs: m.show_viewport = True
        bpy.context.view_layer.update()
        bad = [r["bone"] for r in rows if r["drag"] or r["pinch"] > 3]
        st = "FAIL" if worst["drag"] > 20 or worst["vol"] < .85 else ("WARN" if bad or worst["vol"] < .93 else "PASS")
        put("bend", st, f"{len(rows)} bones bent 70 deg; worst wrong-side drag {worst['drag']} verts, worst pinch {worst['pinch']} faces, "
            f"lowest volume {worst['vol']:.0%}" + (f"; look at {bad[:8]}" if bad else ""), bones=rows)

    # turnaround sheet: rest row, then posed row (IK targets moved so IK + poles are exercised)
    tgt = Vector((0, 0, max(p.z for p in pts) * .5)); h = max(p.z for p in pts)
    cam_d = bpy.data.cameras.new("chk"); cam = bpy.data.objects.new("chk", cam_d); sc.collection.objects.link(cam)
    cam_d.lens = 50; sc.camera = cam
    sc.render.engine = "BLENDER_WORKBENCH"; sc.render.resolution_x, sc.render.resolution_y = 400, 600
    sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_cavity = True; sc.display.shading.show_object_outline = True
    sc.render.film_transparent = False
    def shoot(i, ang):
        a = math.radians(ang); d = h * 2.6
        cam.location = (d * math.sin(a), -d * math.cos(a), h * .62)
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = str(Path(out) / f"view_{i}.png"); bpy.ops.render.render(write_still=True)
    angles = (0, 45, 90, 180)
    for i, a in enumerate(angles): shoot(i, a)
    if arm:   # move IK targets in armature space: left hand up, right hand forward, left knee raised
        from mathutils import Matrix
        goals = {"hand_ik.l": (.28 * h, -.05 * h, .95 * h), "hand_ik.r": (-.12 * h, -.32 * h, .62 * h), "foot_ik.l": (.09 * h, -.22 * h, .28 * h)}
        for pb in arm.pose.bones:
            g = goals.get(pb.name.lower())
            if g: pb.matrix = Matrix.Translation(Vector(g)) @ pb.bone.matrix_local.to_3x3().to_4x4(); bpy.context.view_layer.update()
    for i, a in enumerate(angles): shoot(i + 4, a)

    ok = all(c["status"] != "FAIL" for c in checks.values())
    Path(out, "check.json").write_text(json.dumps({"pass": ok, "checks": checks}, indent=1), "utf8")
    print("CHECK", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    if "bpy" in sys.modules or "--" in sys.argv and Path(sys.argv[0]).name.lower().startswith("blender"):
        a = sys.argv[sys.argv.index("--") + 1:]
        inside(a[1], a[2])
    elif len(sys.argv) == 3:
        sys.exit(host(sys.argv[1], sys.argv[2]))
    else:
        sys.exit(__doc__)

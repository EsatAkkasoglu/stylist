"""Rig-ready PROXY body for a character: the blockout you refine, never the finished character. It gives correct
proportions, a clean quad base with loops at the joints, a named .L/.R armature with IK + poles and automatic weights,
so animation and the 2D layer can start while the real model is still being built (proxy first, swap later).

  python character_blockout.py spec.json out.blend [out.glb]

spec.json (every field optional; units metres, "heads" = body height in head heights: chibi 3, cartoon 5, real 7.5, hero 8.5):
  {"name": "courier", "height": 1.75, "heads": 6.5, "build": 1.0, "shoulders": 1.0, "hips": 1.0, "limbs": 1.0,
   "head": 1.0, "hands": 1.0, "feet": 1.0, "a_pose_deg": 45,
   "colors": {"skin": "#D9A27E", "top": "#3E6FA8", "bottom": "#2B2F35", "shoes": "#1B1B1F"}}

What it does, in the order a technical artist would:
  1. left half + centre line as a skin graph (A-pose, facing -Y, feet on Z=0, centred on X), extra rings beside every
     joint (shoulder, elbow, wrist, hip, knee, ankle, neck) so it bends without pinching
  2. Mirror (clipping, merge) -> Skin -> applied to quads -> cut at X=0 -> Mirror modifier again: the half you edit
  3. Principled materials by region, Smart UV, smooth shading, Subdivision (non-destructive, after the Armature)
  4. before rigging: Mirror applied, transforms applied (rotation 0, scale 1)
  5. armature from the same graph: root, spine, chest, neck, head, shoulder/upper_arm/forearm/hand, thigh/shin/foot (.L/.R),
     rolls recalculated, display In Front; IK (chain 2) with hand_ik/foot_ik targets and elbow/knee poles
  6. automatic weights, Preserve Volume on; out.glb (optional) gets Subdivision applied for export
Then run character_check.py on out.blend and open its sheet.
"""
import json, math, sys
from pathlib import Path


def host(spec, blend, glb=None):
    sys.path.insert(0, str(Path(__file__).parent))
    from mesh_export import run_blender
    return run_blender(__file__, spec, blend, *([glb] if glb else []), show=("BLOCKOUT", "Error", "Traceback", "  File"))


# ------------------------------------------------------------------ inside Blender
def build(spec_path, blend, glb=None):
    import bpy, bmesh
    from mathutils import Vector
    S = {"name": "character", "height": 1.75, "heads": 7.0, "build": 1.0, "shoulders": 1.0, "hips": 1.0, "limbs": 1.0,
         "head": 1.0, "hands": 1.0, "feet": 1.0, "a_pose_deg": 45,
         "colors": {"skin": "#D9A27E", "top": "#3E6FA8", "bottom": "#2B2F35", "shoes": "#1B1B1F"}}
    S.update(json.loads(Path(spec_path).read_text("utf8")) if Path(spec_path).exists() else {})
    H, hh = S["height"], S["height"] / S["heads"]                  # body height, head height
    chin = H - hh
    k = chin / (H * (1 - 1 / 7.5))                                # landmarks below the chin follow a 7.5-head figure, rescaled
    y = lambda f: f * H * k                                       # fraction of a real body height -> metres
    b, L = S["build"], S["limbs"]
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 1. skin graph: (name, position, radius); left side x > 0, front = -Y
    P = {}
    def pt(n, x, yy, z, r): P[n] = (Vector((x, yy, z)), r * b)
    sw, hw = .19 * H * S["shoulders"] * k ** .5, .085 * H * S["hips"]
    pt("pelvis", 0, 0, y(.53), .105 * H * S["hips"]); pt("spine", 0, 0, y(.62), .095 * H)
    pt("chest", 0, 0, y(.72), .11 * H * S["shoulders"]); pt("neck_base", 0, 0, chin - .045 * H * k, .055 * H)
    pt("neck", 0, 0, chin - .01 * H, .042 * H)
    pt("head", 0, -.01 * H, chin + hh * .45, hh * .42 * S["head"]); pt("head_top", 0, -.005 * H, H - hh * .08, hh * .3 * S["head"])
    pt("clav", sw * .45, 0, y(.80), .05 * H)
    a = math.radians(S["a_pose_deg"]); d = Vector((math.cos(a), 0, -math.sin(a)))
    sh = Vector((sw, 0, y(.805))); el = sh + d * (.172 * H * L * k) + Vector((0, .012 * H, 0)); wr = el + d * (.157 * H * L * k)
    pt("shoulder", *sh, .052 * H); pt("elbow", *el, .036 * H * L ** .5); pt("wrist", *wr, .026 * H * L ** .5)
    pt("hand_end", *(wr + d * (.10 * H * S["hands"] * k)), .03 * H * S["hands"])
    hp = Vector((hw, 0, y(.50))); kn = Vector((hw * .95, -.012 * H, y(.285))); an = Vector((hw * .9, 0, y(.045)))
    pt("hip", *hp, .07 * H); pt("knee", *kn, .05 * H * L ** .5); pt("ankle", *an, .035 * H * L ** .5)
    pt("toe", hw * .9, -.13 * H * S["feet"], .02 * H, .035 * H * S["feet"])
    chain = [("pelvis", "spine"), ("spine", "chest"), ("chest", "neck_base"), ("neck_base", "neck"), ("neck", "head"),
             ("head", "head_top"), ("chest", "clav"), ("clav", "shoulder"), ("shoulder", "elbow"), ("elbow", "wrist"),
             ("wrist", "hand_end"), ("pelvis", "hip"), ("hip", "knee"), ("knee", "ankle"), ("ankle", "toe")]
    JOINT = {"shoulder", "elbow", "wrist", "hip", "knee", "ankle", "neck"}
    verts, rads, edges, idx = [], [], [], {}
    def add(p, r): verts.append(p); rads.append(r); return len(verts) - 1
    for n, (p, r) in P.items(): idx[n] = add(p, r)
    for a_, b_ in chain:   # rings either side of a joint (8 % of the bone) = the deformation loops
        pa, ra = P[a_]; pb, rb = P[b_]; seq = [idx[a_]]
        for t in ([.08] if a_ in JOINT else []) + [.5] + ([.92] if b_ in JOINT else []):
            seq.append(add(pa.lerp(pb, t), ra + (rb - ra) * t))
        seq.append(idx[b_]); edges += list(zip(seq, seq[1:]))
    me = bpy.data.meshes.new("body"); me.from_pydata([tuple(v) for v in verts], edges, []); body = bpy.data.objects.new(S["name"], me)
    bpy.context.collection.objects.link(body); bpy.context.view_layer.objects.active = body; body.select_set(True)
    mi = body.modifiers.new("Mirror", "MIRROR"); mi.use_clip = True; mi.use_mirror_merge = True
    sk = body.modifiers.new("Skin", "SKIN"); sk.branch_smoothing = .4; sk.use_smooth_shade = True
    for i, sv in enumerate(me.skin_vertices[0].data):
        sv.radius = (rads[i], rads[i])
    me.skin_vertices[0].data[idx["pelvis"]].use_root = True
    bpy.ops.object.modifier_apply(modifier="Mirror"); bpy.ops.object.modifier_apply(modifier="Skin")

    # 2. clean quads, cut at X=0, mirror back as the editable half
    bm = bmesh.new(); bm.from_mesh(body.data)
    bmesh.ops.join_triangles(bm, faces=[f for f in bm.faces if len(f.verts) == 3], angle_face_threshold=math.radians(40), angle_shape_threshold=math.radians(40))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_inner=True)
    for v in bm.verts:
        if abs(v.co.x) < 1e-4: v.co.x = 0
    flat = [f for f in bm.faces if all(v.co.x == 0 for v in f.verts)]   # hull faces lying in the mirror plane: Mirror would double them
    if flat: bmesh.ops.delete(bm, geom=flat, context="FACES_ONLY")
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    ng = [f for f in bm.faces if len(f.verts) > 4]
    if ng: bmesh.ops.triangulate(bm, faces=ng)
    bmesh.ops.join_triangles(bm, faces=[f for f in bm.faces if len(f.verts) == 3], angle_face_threshold=math.radians(60), angle_shape_threshold=math.radians(60))
    for v in bm.verts:
        if abs(v.co.x) < 1e-4: v.co.x = 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(body.data); bm.free()
    mi = body.modifiers.new("Mirror", "MIRROR"); mi.use_clip = True; mi.use_mirror_merge = True; mi.use_mirror_vertex_groups = True

    # 3. materials by height band, UVs, smooth
    def mat(name, hexc):
        m = bpy.data.materials.new(name); m.use_nodes = True
        c = tuple(int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5)) + (1,)
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = c; m.diffuse_color = c
        body.data.materials.append(m)
    for n in ("skin", "top", "bottom", "shoes"): mat(f"{S['name']}_{n}", S["colors"][n])
    for p in body.data.polygons:
        c = body.matrix_world @ p.center; ax = abs(c.x)
        p.material_index = (3 if c.z < y(.06) else 0 if c.z > chin - .02 * H or (ax > sw + .1 * H * L * k) else
                            1 if c.z > y(.50) else 2)
        p.use_smooth = True
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.02); bpy.ops.object.mode_set(mode="OBJECT")

    # 4. before rigging: mirror applied, transforms applied
    bpy.ops.object.modifier_apply(modifier="Mirror")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    # 5. armature from the same landmarks
    ad = bpy.data.armatures.new(f"{S['name']}_rig"); arm = bpy.data.objects.new(f"{S['name']}_rig", ad)
    bpy.context.collection.objects.link(arm); ad.display_type = "OCTAHEDRAL"; arm.show_in_front = True
    bpy.ops.object.select_all(action="DESELECT"); bpy.context.view_layer.objects.active = arm; arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT"); eb = ad.edit_bones
    def bone(n, h, t, parent=None, deform=True, connect=False):
        e = eb.new(n); e.head, e.tail = h, t; e.use_deform = deform
        if parent: e.parent = eb[parent]; e.use_connect = connect
        return e
    p = lambda n: P[n][0]
    bone("root", Vector((0, 0, 0)), Vector((0, .25 * H, 0)), deform=False)
    bone("spine", p("pelvis"), p("spine"), "root"); bone("spine.001", p("spine"), p("chest"), "spine", connect=True)
    bone("chest", p("chest"), p("neck_base"), "spine.001", connect=True)
    bone("neck", p("neck_base"), p("neck"), "chest", connect=True); bone("head", p("neck"), p("head_top"), "neck", connect=True)
    bone("shoulder.L", p("clav"), p("shoulder"), "chest"); bone("upper_arm.L", p("shoulder"), p("elbow"), "shoulder.L", connect=True)
    bone("forearm.L", p("elbow"), p("wrist"), "upper_arm.L", connect=True); bone("hand.L", p("wrist"), p("hand_end"), "forearm.L", connect=True)
    bone("thigh.L", p("hip"), p("knee"), "spine"); bone("shin.L", p("knee"), p("ankle"), "thigh.L", connect=True)
    bone("foot.L", p("ankle"), p("toe"), "shin.L", connect=True)
    up = Vector((0, 0, .08 * H)); fwd = Vector((0, -.08 * H, 0))
    bone("hand_ik.L", p("wrist"), p("wrist") + d * .08 * H, "root", deform=False)
    bone("elbow_pole.L", p("elbow") + Vector((0, .35 * H, 0)), p("elbow") + Vector((0, .35 * H, 0)) + up * .5, "root", deform=False)
    bone("foot_ik.L", p("ankle"), p("ankle") + fwd, "root", deform=False)
    bone("knee_pole.L", p("knee") + Vector((0, -.4 * H, 0)), p("knee") + Vector((0, -.4 * H, 0)) + up * .5, "root", deform=False)
    bpy.ops.armature.select_all(action="SELECT"); bpy.ops.armature.calculate_roll(type="GLOBAL_NEG_Y")
    bpy.ops.armature.select_all(action="DESELECT")
    for e in eb:
        if e.name.endswith(".L"): e.select = e.select_head = e.select_tail = True
    bpy.ops.armature.symmetrize(direction="POSITIVE_X")
    bpy.ops.object.mode_set(mode="POSE")
    for s_ in ("L", "R"):
        for bn, tg, pole, ang in ((f"forearm.{s_}", f"hand_ik.{s_}", f"elbow_pole.{s_}", -90), (f"shin.{s_}", f"foot_ik.{s_}", f"knee_pole.{s_}", -90)):
            c = arm.pose.bones[bn].constraints.new("IK"); c.target = arm; c.subtarget = tg
            c.pole_target = arm; c.pole_subtarget = pole; c.pole_angle = math.radians(ang); c.chain_count = 2
    bpy.ops.object.mode_set(mode="OBJECT")

    # 6. automatic weights, Preserve Volume, then Subdivision after the Armature (non-destructive)
    bpy.ops.object.select_all(action="DESELECT"); body.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    am = next(m for m in body.modifiers if m.type == "ARMATURE"); am.use_deform_preserve_volume = True
    # bone heat leaks across the crotch and armpits: a .L bone may not move vertices on the right, and the reverse
    gname = {g.index: g.name for g in body.vertex_groups}
    for v in body.data.vertices:
        for g in list(v.groups):
            n = gname[g.group]
            if (n.endswith(".L") and v.co.x < -.01) or (n.endswith(".R") and v.co.x > .01):
                body.vertex_groups[n].remove([v.index])
        tot = sum(g.weight for g in v.groups)
        for g in v.groups:
            if tot > 0: g.weight /= tot
    # pole angle: pick the one that leaves the chain exactly in its rest pose
    for pb in arm.pose.bones:
        for c in pb.constraints:
            if c.type != "IK": continue
            def err(ang):
                c.pole_angle = math.radians(ang); bpy.context.view_layer.update()
                return sum((q.matrix - q.bone.matrix_local).to_3x3().to_quaternion().angle for q in (pb, pb.parent))
            c.pole_angle = math.radians(min(range(-180, 180, 1), key=err)); bpy.context.view_layer.update()
    sub = body.modifiers.new("Subdivision", "SUBSURF"); sub.levels = 1; sub.render_levels = 2
    coll = bpy.data.collections.new(S["name"]); bpy.context.scene.collection.children.link(coll)
    for o in (body, arm):
        for c in o.users_collection: c.objects.unlink(o)
        coll.objects.link(o)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print(f"BLOCKOUT {S['name']}: {len(body.data.polygons)} cage faces, {len(ad.bones)} bones -> {blend}")
    if glb:
        bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_apply=True, export_skins=True)
        print(f"BLOCKOUT glb -> {glb}")


if __name__ == "__main__":
    if "bpy" in sys.modules:
        a = sys.argv[sys.argv.index("--") + 1:]
        build(*a[1:])
    elif len(sys.argv) in (3, 4):
        sys.exit(host(*sys.argv[1:]))
    else:
        sys.exit(__doc__)

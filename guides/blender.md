# Blender production: characters, props and the way the work is run

For any film that builds 3D in the user's own Blender (guide "3d", Mode C, or props). Everything runs locally and free:
no paid generators, no stock or model sites, no rented GPUs. Music is written as notes (guide "music"), sounds come
from `search_sfx` (guide "sound"). Find Blender with `python kit/blender/mesh_export.py --check`; if it is missing,
say so and use Mode B from guide "3d".

## 1. You cannot see your work, so measure it

Every claim about a model ("quad-only", "symmetric", "bends cleanly") is something a tool reported, never something
a script was written to do. After every build step, run the check, open the picture it makes, and fix what it names.

- Characters: `python kit/blender/character_check.py model.blend out/check` must PASS. Then **open `sheet.png`**
  (rest row, posed row) and look for what numbers miss: silhouette, proportions, a joint folding the wrong way.
- Props: a 12-angle turnaround, closed and apart (`mesh_export.py` + your renderer), before animating.
- Video: contact sheets and gates G0–G6 (guide "motion"); sound: `audio/audio_report.py`. Say in the README what you
  could not check (you do not hear the mix or watch the film the way a person does).

## 2. Characters: from a description to an animation-ready model

Turn the user's description into numbers first, then build in this order. Do not skip a step to save time; a rig on
an untidy mesh costs more later.

1. **Spec.** Proportions in head heights (chibi 3, cartoon 5, realistic 7.5, heroic 8.5), build, shoulder/hip width,
   limb thickness, head size, colours by region. Ask for a reference picture if the user has one; model beside it.
2. **Proxy first.** `python kit/blender/character_blockout.py spec.json char.blend char.glb` gives a rig-ready
   stand-in in a minute: A-pose facing -Y, feet on Z=0, centred on X, quads, loops beside every joint, named
   `.L/.R` armature, IK with poles, automatic weights, Preserve Volume. Animation, camera and the 2D layer start on
   the proxy now; the real model replaces it later in the same place, and the animation is not redone.
   The proxy is a mannequin, not the character. Never deliver it as the character.
3. **The real model**, on top of the proxy's proportions:
   - Model one half; a Mirror modifier with Clipping (and Merge) on X keeps the centre seam closed and symmetric.
   - Quads only, manifold, no overlapping vertices, normals outward. Add edge loops where the body bends: shoulders,
     elbows, wrists, hips, knees, ankles; around the eyes and the mouth when the face is seen close up.
   - Subdivision Surface and smooth shading stay as modifiers (non-destructive).
   - Hard accessories (armour plates, helmet, buttons, tools) are separate objects parented to a bone, not weighted:
     they stay rigid and never stretch.
   - Principled BSDF materials named by region (`<name>_skin`, `<name>_jacket`); UVs unwrapped (Smart UV is fine for
     flat colour, seams by hand for textures). Name every object, collection and material.
4. **Before rigging:** apply the Mirror, then apply rotation and scale (scale 1,1,1). Keep the stylised look in the
   mesh, never in an object scale.
5. **Rig.** Bones from the root up (spine, chest, neck, head, limbs), `.L/.R` names only, built on the left and
   symmetrised on X, rolls recalculated so every joint bends on one axis, display In Front. IK on arms and legs (chain
   2) with pole targets; choose the pole angle that leaves the rest pose unchanged (the blockout script does this).
   Automatic weights, then remove any `.L` weight on the right half and any `.R` weight on the left (bone heat leaks
   across the crotch and the armpits), then normalise. Armature modifier with Preserve Volume, above Subdivision.
6. **Check** (step 1 of this guide). Typical findings and their fix:
   - wrong-side drag: a leg or arm pulling the other side → the side clean-up above, or paint it off.
   - pinch at a joint → one more loop beside that joint, or move the existing loops to straddle the pivot.
   - volume under 90 % on a bend → Preserve Volume on, or a corrective loop.
   - asymmetric mesh → something was edited after the Mirror was applied; redo it on the half.
7. **Export.** glTF has no IK: bake the animation to keys on export (the exporter samples constraints) and apply
   Subdivision for the export copy. Check the GLB: one skin, all joints, `JOINTS_0`/`WEIGHTS_0` present.

If the user picked a style whose renderer is not Blender (for example an ink renderer in the project), export the
posed mesh per frame with `mesh_export.py` and draw it in the style; the look stays the style's.

## 3. Props and machines

One object per real part so it can come apart (`part(obj, name, colour)`), modelled from a reference, scaled to the
real object, turnaround checked closed and apart. Parts come apart along varied directions with small tilts, never
in a ruler-straight line. Inside parts that only show when it opens are hidden while it is closed.

## 4. How the work is run

- **One timeline, decided first.** The music is written and measured before anything is animated; its tempo and the
  frame of every beat sit in one timeline file that every scene reads.
- **Gates, cheapest first.** Concept in 5–8 lines + 3–4 style frames → a full-length animatic at 540p with the music
  → the first full assembly → the final. These are the style frame, the 15–30 s demo and gates G0–G6 of the brief,
  not a second numbering. The user sees each one and answers before the next starts.
- **Previews small, final once.** Previews at 960×540 (Workbench or few samples, key frames only). Lock the
  animation, then render the final frames once at full size with denoising. Long renders go through one queue, one
  job at a time, in chunks of a few minutes so a preview never waits behind a final.
- **2D over 3D is a separate pass.** Type, tags and glitches are drawn over the renders in code, so a note on the 2D
  layer never needs a 3D re-render. A note on a few seconds re-renders only those frames.
- **Never overwrite a delivery.** Every fix is a new file next to the old one (`film-v1.mp4`, `film-v2.mp4`).
- **Encode with the colour tagged** (`-colorspace bt709 -color_primaries bt709 -color_trc bt709`), or colours drift
  between players.
- **Helpers only when the user asks for them.** If they do: one lead owns the timeline and the quality; each helper
  gets one part as a direct message and stops when it hands it in; a proxy assembly exists early so nobody waits.
- **README:** what was made, how to rebuild it, the checks that passed, and an honest list of weak points. In a
  making-of cut, list what is real (models, renders, timings) and what is drawn (a code-drawn app window, cursors).

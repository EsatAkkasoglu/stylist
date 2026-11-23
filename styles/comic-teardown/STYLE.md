# Comic Teardown — Style Prompt

> A real object taken apart on a real workbench, drawn like a clean comic panel: ink contours with a clear line hierarchy, flat colour, hatching instead of gradients. The layers lift on one axis, the camera dives into the part that matters, and each idea of the voice becomes one object you could hold.
> References (grammar only): hand-inked explainer shorts, repair-guide teardowns, ligne-claire comics, engineering exploded views. Never copy their products, layouts, typefaces or music, or name them in the film.

## 1. Essence, and what it is not

A frame reads as this style when:

- **it is drawn, not photographed**: every surface is one flat colour plus at most one shade tone; light is shown with ink (hatching, cast-shadow hatching), never with gradients or bloom;
- **the line has a hierarchy**: a thick silhouette around each object, thinner feature edges, finest interior detail; you can tell the objects apart by line weight alone;
- **it happens somewhere**: a workbench with a blue cutting mat, a wooden edge, a pegboard with tools, a pale wall. The object lies on it and casts a hatched shadow on it;
- **it comes apart**: layers float on one axis, in order, each in the orientation it has in the product, with an even gap and its own shadow on the mat;
- **numbers are written into the scene**: a short heavy caption in the air above the object ("4 screws") or a paper tag on a leader line; never a table beside it.

It is not the photoreal Exploded Teardown (PBR, dark studio, no environment), not a blueprint (line on grid, no colour), not an assembly manual (step numbers, hands, flat page), not a cartoon with characters (no faces, no mascots: the objects are the actors).

## 2. Drawing & rendering

- **Space**: true perspective (3D scene projected by a camera, 3D mode A), focal length around 35–50 mm equivalent, horizon usually above the frame so we look down at the bench at 30–55°.
- **Line hierarchy** (at 1080 px frame width; scale with width):
  | Edge | Width | Ink |
  |---|---|---|
  | Object silhouette | 5 px | full ink |
  | Feature edge (fold of a box, rim of a hole) | 2.5 px | full ink |
  | Interior detail (fins, traces, screws, grid) | 1.2–1.6 px | 70–85 % ink |
  | Environment (mat grid, wood grain, pegboard holes) | 1–2 px | 35–60 % ink or a darker tint of the surface |
  | Hidden edges | none | — |
- **Fill**: each material is one flat colour. Faces turned away from the key light take the same colour darkened 12–20 %; the face furthest from the light also gets hatching. Never a gradient across a face.
- **Hatching**: parallel ink lines, 1.2 px, every 8–10 px, at one fixed angle for the whole film (about 60° from horizontal), 30–45 % ink. Cast shadows on the mat and wall are hatching over a 10 % darker tint, with a hard edge, offset along the light direction.
- **Paper**: a faint grain (2–3 % luminance noise) over everything, fixed per frame, not boiling.
- **Objects**: modelled from published dimensions, simplified to the parts that tell the story (boards, plates, fins, pipes, fans, chips). Repeated parts (screws, fins, chips, droplets) are drawn individually, not as textures. No logos or trademarks on parts.
- **Wall mark (optional)**: the channel or brand name painted on the wall behind the bench like an old workshop sign: a bold condensed grotesque (Bahnschrift Bold Condensed), lower-case, one tint darker than the wall at 50–70 % strength, worn paint (roller streaks, chipped patches), in true perspective on the wall plane. It is part of the set: it never animates, never sits in front of the object, and the bench props may cover it.
- **Scale props** come from the same world: a tank, a plane, a bus, a map are drawn as desk-sized toys or paper cut-outs on the same bench, so the film never leaves the workbench.

## 3. Colour logic

- The environment is pale and low-saturation; the product carries the only saturated colours; one accent (warm yellow) marks the thing being counted or pointed at.
- The wall carries a faint plaster texture (low-frequency mottling, 20 % overlay); every other surface stays flat.
- Values are ordered: wall and pegboard lightest, mat mid, product mid-to-dark with saturated local colours, ink darkest.
- Palette of our demo: ink #1E2126 · wall #CFE3D6 · pegboard #EAD6AE (holes #7A6A55) · mat #8CB2D3 (grid #5E86AC) · wood #E7C998 (grain #B48F5C) · steel #C9CDD2 · dark plastic #3A3F47 · board green #2F9B57 · copper #D9783C · red #DD4F3A · accent #F4C431 · paper tag #FBF7EE.

## 4. Type & subtitles

- **Captions in the scene**: a heavy black grotesque (Arial Black or Archivo Black), lower-case where possible, 60–90 px, ink black with a thin paper-coloured halo (16 % of the size, 85 % strength) so it stays clean over the wall mark, set in the air above the object in the free area of the frame. One caption at a time, at most four words, only numbers the voice says ("4 screws", "76.3 billion").
- **Tags**: a paper tag (#FBF7EE, 2.5 px ink border, small corner cut) on a 2 px leader whose dot lands on the part; name in the heavy face 34–40 px, one spec line in a monospaced face 26–30 px (JetBrains Mono or Consolas). Units always written.
- **Subtitles** (when used): bottom 14 % of a 9:16 frame, white heavy face with a 6 px ink stroke, two lines max, words appear as they are spoken.
- Text never sits on hatching; move it, or put it on a tag.

## 5. Motion quality

- 24 fps; the camera moves on ones; objects that animate mechanically (screws turning, layers lifting) also on ones; captions pop in over 3 frames (scale 0.85 → 1.04 → 1).
- **Separation**: top layer first, 0.15–0.25 s apart, ease-in-out cubic, a 2–4 frame settle; repeated parts (screws) leave in order, each with a quarter turn before it lifts.
- **Apart is never ruler-straight**: each separated layer drifts 1–4 cm sideways and tilts 2–6° on its own axes, so the stack reads as parts lifted by hand, not a CAD explode. Repeated parts fan out and spread (three fans: different heights, 8–13° tilts, wider spacing than when mounted). Gaps stay readable and the order stays clear.
- **Held apart**: layers float 1–2 % of their gap with offset phases; their shadows breathe with them.
- **Closing**: bottom first, faster, the last part lands without bounce (metal does not rubber-bounce).
- **Never moves**: the bench, the light direction, the hatching angle.

## 6. Camera grammar

| Move | What it expresses | Can serve |
|---|---|---|
| High three-quarter on the bench | the object in its world | an opening; a question |
| Orbit while layers separate | order of assembly | a teardown |
| Push down into one part | "look closer" | a chip, a die, a seal |
| Match-zoom through a part into a new scale | the next level of the answer | die → layers → wires; machine → droplet |
| Slow lateral track along a row of objects | comparison | counts, sizes, alternatives |
| Pull back up to the whole bench | synthesis | a closing; everything we just saw |

- Transitions are camera moves: a push into a part that becomes the next scene, a pan along the bench to the next prop. No cuts to black, no wipes, no split screens.
- In 9:16 the object sits in the middle third; captions in the upper third; subtitles in the bottom 14 %.

## 7. Sound palette

- Every sound has a visible cause and a material: a screwdriver bit engaging and the screw ticking out (metal on metal), a bracket set down on the mat (dull plastic/metal on rubber), a fan blade flicked (light plastic), paper tags rustling, a toy set on the bench (wood/plastic thud).
- No swooshes, risers or sweeps for camera moves: the camera is silent. A camera move with no physical event has no sound.
- Room tone of a quiet workshop under everything; two near-silences before the biggest reveals.
- Music: tuned mallets (marimba, vibraphone, glockenspiel), a round bass, no drums; it sits about 10 dB under the voice and leaves gaps where the voice lands a number.
- Mix: voice on top, −14 LUFS integrated, true peak −1.5 dBFS.

## 8. Native moves

- **Screw out, lift off.** Four screws turn a quarter, rise in order, the cover lifts. *Fits:* any first opening.
- **The floating stack.** All layers held apart above the mat, each with its shadow. *Fits:* "what is inside".
- **Into the part.** The camera pushes into a chip, a slot, a lens until it becomes a new scene at a new scale. *Fits:* die, layers, wires; a lens; a cell.
- **Desk-toy comparison.** Toy-sized props (a tank, a plane) set down next to the product with a counter tag each. *Fits:* counts, sizes, costs.
- **Peel.** Layers of one part lift off one by one like sheets. *Fits:* chip layers, paint, geology.
- **Count apart.** When the voice gives a part count, that object comes apart into its own parts on the word. *Fits:* hundreds vs thousands vs millions of parts.
- **Into the eyepiece.** The part goes under a microscope, the camera travels into the eyepiece and the plan draws itself as a diagram. *Fits:* die plans, cells, fibres.
- **Area sweep.** A spoken area sweeps across the part and fills it, the number riding the edge. *Fits:* die size, sensor size, footprint.
- **Back on the bench.** The film ends where it began, the object closed or still apart, with the one thing the viewer should remember as a caption.

## 9. Pitfalls of the medium

- **Equal line weights.** Everything at one width reads as clip art. Fix: the hierarchy table, checked on a still.
- **Floating with no shadow.** A part in the air without a cast shadow reads as pasted. Fix: every object casts a hatched shadow on the mat.
- **Gradient creep.** Soft shading makes it look like a cheap 3D render. Fix: flat fills, two tones, hatching.
- **Busy hatching.** Hatching on every face turns the frame grey. Fix: only the darkest face and cast shadows.
- **Painter's-order errors.** Faces drawn in the wrong order poke through. Fix: sort per object then per face, split objects that interpenetrate.
- **Invented numbers or logos.** Fix: show only what the voice says and FACTS.md backs; plain parts.
- **Parallel, linear explode.** Layers stacked perfectly parallel and centred look like a CAD export. Fix: per-layer drift and tilt (§5).
- **Primitive models.** A box called "machine" is not a machine. Fix: a model sheet before animation, compared side by side with a reference.

## 10. Modelling, staging and sync (lessons from the first film)

**Models.** Anything more complex than a plate or a box (vehicles, instruments, machines) is modelled in Blender when the user has it, with a bpy script, and exported as geometry only (kit `blender/mesh_export.py`); this renderer still draws it, so the look stays the same. Without Blender, build it from the engine's primitives with the same care.
- Model beside a reference picture: proportions, part count, the parts a viewer expects to recognise (a tank: hull with sloped plates, turret, barrel with muzzle brake, road wheels, sprockets, track; an airliner: tapered fuselage, swept wings, engine nacelles, fin and tailplane, a row of windows; a microscope: base, arm, stage with clips, objective turret, tube, eyepiece, focus knobs).
- Every model is split into its real parts, each its own object, so it can come apart; each part keeps its true position in the assembly.
- Turnaround check before animation: 12 angles, closed and apart; any face poking through, missing outline or floating part fails.
- Line weight per edge: silhouette 5 px, crease (angle > 30°) 2.5 px, smooth edges none.

**Staging.**
- One subject per shot. At key moments it fills at least a third of the frame height; never a toy lost at the back of a wide shot.
- At most one caption and one tag on screen; the caption band never overlaps the wall mark (move the camera or the caption, not a halo).
- A prop enters on the word that names it, by motion, never by appearing: alternate sides (the first from the right, the next from the left), slide or drop in, land with weight and its sound.
- A count is shown, not only written: when the voice gives "hundreds / thousands / millions of parts", that object comes apart into its own parts on that word, so the difference is seen.
- A number spoken about a part gets an animation on that part: an area sweeps across a die and fills it, a length draws its dimension line, a count ticks up beside the thing counted. Show only what the voice gives (an area, not invented side lengths).
- When the voice names a tool or an action ("put it under a microscope", "peel it layer by layer"), build the tool and do the action literally: the chip is set on the microscope stage, the camera travels into the eyepiece, the plan draws itself as a diagram.

**Continuity.**
- Nothing pops in or out: objects enter and leave by motion, scale never changes while visible, layers that are peeled fly out of frame before they are removed.
- Transitions between scales happen through the object (the camera passes through the eyepiece, the hatch, the die), with matched colour; no full-frame colour fades.
- After rendering, scan frame-to-frame differences; every spike above ~15× the median is looked at and is either a deliberate hit or fixed.

**Sync.**
- Every visual beat hangs on a word timestamp from the voice (a cue table built by word index from the transcript). Order on screen follows the order of the words.
- If the voice is retimed (speed change), re-transcribe and rebuild the cue table; never scale old times by hand.

## 11. Workflow rules (from our lessons)

1. **Model sheet first**: the hero object is drawn as one still, compared side by side with a reference picture (proportions, part count, nothing floating) and shown to the user before animation; at least two fix rounds.
2. **Script approved before render**: shot table timed to the voice's word timestamps.
3. **Facts file**: FACTS.md with every number on screen and its source.
4. **Fonts**: if the style's font is missing, ask before downloading or falling back.

## 12. Engine

`demo/comic-teardown-film/engine.py` (skia-python + numpy): a small perspective renderer for boxes, plates with holes, tubes and flat polygons; per-object painter's order; line hierarchy; hatched shade faces and cast shadows on the bench; the workbench set; captions and tags.

## 13. Variation space

Decided per film: the object, the order of opening, which part gets the dive, the props that carry comparisons, the accent colour, vertical or horizontal.

- **Openings**: the closed object on the bench with a question caption; a single screw turning in macro; the stack already apart, slowly closing.
- **Endings**: everything apart and labelled like a printable sheet; closed again with one caption; the camera pulling back to the whole bench with the props of the film on it.


---

## Stylist layer

Added by Stylist on top of the rules above. **The look** (palette, type, drawing, materials, atmosphere) is the rules above, unchanged.
**Camera, motion and pacing** follow the Stylist cinematic standard (guide "motion"): a virtual camera that never rests, camera-based
transitions, idle life on everything on screen, three depth layers with parallax, staggered spring/ease-out entrances. Where the rules
above name a camera move or transition, keep it and run it on that rig. Music genre and level follow guide "music".

**SFX families** (call `search_sfx` with these; 3–4 families for the whole film, guide "sound"):
- `FOLEY/MECHANICAL` — search word "screwdriver"
- `FOLEY/MECHANICAL` — search word "metal"
- `IMPACT/HIT` — search word "wood"
- `FOLEY/PAPER` — search word "paper"

**Motion profile**: camera rig `calm` (kit `motion/motion_pro.js` `RIGS`); continuous camera through the object; typical move 10–16 frames; default curve `softLand`, never linear; text reveal `pop` (kit `reveal()`, words staggered, exits backwards); motion blur on fast camera moves off: this look stays crisp. Gates G0–G6 before the full render.

**Music (made by default, guide "music")**: tuned mallets and glass, a round bass, no drums. Write it as notes and play it with kit `audio/notes.py` (MusicXML + General MIDI), space `hall`. Band: lead vibraphone (GM 11), pad marimba (GM 12), pulse glockenspiel (GM 9), bass synthbass (GM 38), sparkle glass (GM 92). Drums: none: the comping instruments keep time. Groove reference `minimal-pulse`. Band, engine and space are in style.json `stylist.score.render`; the **topic** picks mood, tempo and key. The customer can ask for another genre or no music.

**3D mode**: A (guide "3d": none = 2D only, A = SVG extruded, B = skeletonless / rigid joints; never outside 3D sites).

**Formats**: 9:16, 16:9, 1:1.

**Notes from Stylist**: Our own style (not from lemo-opuscar). Sounds: material foley with a visible cause only; no swooshes or sweeps.

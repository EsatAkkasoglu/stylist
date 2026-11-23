# Motion: editing rhythm, easing, quality gates

The library already renders each frame as a pure function of time (`window.render(t)`, see `core/README.md`). Keep it that way: no `requestAnimationFrame`, no `Date.now()`, no state carried between frames. Every value is computed from `t` (or `frame / fps`).

## The cinematic standard (every style)

The style keeps its look (palette, type, drawing, materials, atmosphere) exactly. Camera, motion and pacing follow these five
rules, at the strength of the style's rig (`style.json` `stylist.motion.rig`: `calm`, `editorial` or `punchy`; kit `motion/motion_pro.js` `RIGS`).

1. **Virtual camera rig.** No static shot. Every scene sits under a camera that always moves: `rig(t, cuts, RIGS.<rig>, { hits, fps })`
   gives a continuous drift, a slow push per shot (cosine, never linear) and the move into the next shot. Apply it on top of the
   scene's own camera move (the one plan_edit picked from STYLE.md). Shots are joined by a camera move, not a plain cut:
   `calm` = push-through with a focus pull, `editorial` = slide, `punchy` = snap zoom. A style's own transition (dissolve, iris,
   curtain, ink wipe) stays, and runs while the camera moves. On punch words and when the hero lands: a 4–5 frame decaying
   micro-shake (`hits`, same numbers as plan_edit's "Darbe" column). Fast camera moves (snap zoom, slide, whip) carry motion
   blur: `rig().mb` gives `{ x, y }` in frame widths from the last frame's move (180° shutter, 0 at rest, shake excluded);
   apply it as an SVG `feGaussianBlur stdDeviation="${mb.x*W} ${mb.y*W}"` on the scene group or a canvas smear. Off when
   the style's `stylist.motion.mblur` is false (pixel, dither, stepped looks stay crisp).
2. **Zero dead frames.** After its entrance, nothing is fully still until it leaves: `idle(t, seed)` gives breathing scale, a
   slow float and a slight sway (apply from a stored base pose every frame, never accumulate). Every ~2.75 s a secondary
   micro-action refreshes the eye (`accents(t0, t1)`): a glint, a pulse, a data point lighting, a background layer shift. It
   accents the hero; it never adds a new subject.
3. **Three depth layers with parallax.** Background: slow atmosphere in the style's own material (texture, grid, particles, light
   gradient), ×0.25 of the camera's offset. Middle: the hero and its label, ×1. Foreground: near the lens, soft (depth of field),
   moving light or particles in the style's material, ×1.8. In 3D scenes parallax comes free from real depth; in 2D, multiply
   the camera offset by `LAYERS`.
4. **Choreography.** No linear moves (constant-speed flow, like a current in a wire, is the one exception). Aggressive ease-out
   (`softLand`) or a light overshoot (`spring`, `snapSettle`). Elements of a group enter 4–6 frames apart (`stagger`). Text never
   sits as one block: words enter staggered, and the punch word changes to the style's accent colour, gets an underline that
   draws in, or a small scale pop (`emphasis`), never a card.
5. **Kinetic type in the style's manner.** Each word (or letter, for short titles) appears with the style's reveal,
   `style.json` `stylist.motion.reveal`, kit `reveal(t, stagger(t0, i), kind)`: `wipe` (clip-path, documents and data),
   `rise` (up from below the baseline inside an `overflow:hidden` line), `focus` (blur to sharp, paint and film), `track`
   (letter-spacing closes in, type and posters), `draw` (written on at a steady rate, pen, chalk, terminal, light). The
   reveal is drawn in the style's material when it has one (a brush wipe, a scan line, a chalk stroke). Exits play it
   backwards (`{ out: true }`, ease-in, leave fast). Hold a short line at least 1.5 s after it lands (G3 measures it).

**Clarity still comes first** (guide "creative" §0): subtitles and the step counter sit outside the rig (no shake, no sway);
labels get only a tiny idle and must stay in frame at the rig's extremes (G3); foreground particles never cross a label; a
label tied to a spoken word appears on that word, the stagger goes to the secondary elements.

- **Asymmetric curves.** Ease in slow, leave fast. A typical move is ~10 frames. Things arrive from a scale (1.15 → 1) or from an edge, not from nothing (0 → 1).
- **Licence:** don't use GSAP (its licence isn't open source). Write easing as plain functions, e.g.:

```js
const clamp01 = x => Math.min(1, Math.max(0, x));
const softLand   = x => 1 - Math.pow(1 - clamp01(x), 4);                              // fast start, long soft landing
const snapSettle = x => { const c = 1.70158, u = clamp01(x) - 1; return 1 + (c + 1) * u ** 3 + c * u ** 2; };  // overshoots ~10 %, settles
const accelExit  = x => Math.pow(clamp01(x), 3);                                       // leaves accelerating
const seg = (t, t0, t1) => (t - t0) / (t1 - t0);                                       // local 0..1 for a move
```

- **One-take mode** (product demos, a single camera): no cuts; each beat grows out of the last under one camera matrix. Only when the style or the user asks for it.

## Gates: run before the full render

Render a style frame and a 15–30 s demo first. Only when all gates pass, render the film.
Kit `gates/gates.py` runs G0, G2, G3, G5 and G6 in one go (`python tools/gates.py out/video.mp4 --size 1920x1080 --fps 24 --dur 20 --project <film> --lib $LIB`) and tells you what to look at for G1 and G4. The easing curves, `tween`, `enter`, `drift`, `shot` and the standard's `rig` (with `mb` motion blur), `shake`, `idle`, `stagger`, `accents`, `emphasis`, `reveal` are in kit `motion/motion_pro.js`.

| Gate | Checks | How |
|---|---|---|
| G0 | it renders | `node core/render/video.mjs …` exits 0; `ffprobe` shows the expected size, fps and duration |
| G1 | it looks like the style | `node core/render/still.mjs <project> <t…>`; open the stills and compare them with `STYLE.md` point by point |
| G2 | no dead frames | on the **pre-mux** render from `video.mjs` (mux.sh adds moving grain, which hides frozen frames): `ffmpeg -i out/video.mp4 -vf "freezedetect=n=0.001:d=<3/fps>,metadata=mode=print:file=-" -f null -` → any `freeze_start` you didn't intend fails |
| G3 | text is readable | `node core/render/readcheck.mjs <project>` (needs `window.TEXTS`) |
| G4 | sound sits on the picture | the cue before/after frames from the sound guide |
| G6 | liveness (the standard) | printed by gates.py: near-still seconds (measured on lit pixels; dark areas may rest) and stretches > 3.5 s without a fresh accent. LOOK: every listed time needs a reason (a declared hold) or a fix |
| G5 | nothing leaks (page chrome, scrollbars, cut-off text, blank WebGL) | `python core/render/sheet.py sheet.jpg <stills…>` and **look at the contact sheet**. DOM linters can't read text drawn in a canvas, so this one is your eyes |

Report each gate as pass/fail with the evidence (the command output or the image you looked at).

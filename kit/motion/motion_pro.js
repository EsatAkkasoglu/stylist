// Deterministic motion helpers: every value is a pure function of time, so any frame renders alone (seek-safe).
// Open source, no GSAP. Import in a film page:  import * as M from "./tools/motion_pro.js";
export const clamp01 = x => Math.min(1, Math.max(0, x));
export const lerp = (a, b, k) => a + (b - a) * k;
/** local 0..1 progress of a move that runs from t0 to t1 */
export const seg = (t, t0, t1) => clamp01((t - t0) / (t1 - t0));

// Asymmetric curves: arrive slow, leave fast.
export const ease = {
  linear: x => clamp01(x),
  softLand: x => 1 - (1 - clamp01(x)) ** 4,                                                    // fast start, long soft landing
  snapSettle: x => { const c = 1.70158, u = clamp01(x) - 1; return 1 + (c + 1) * u ** 3 + c * u ** 2; },  // overshoots ~10 %, settles
  accelExit: x => clamp01(x) ** 3,                                                             // leaves accelerating
  inOut: x => { x = clamp01(x); return x < 0.5 ? 4 * x ** 3 : 1 - (-2 * x + 2) ** 3 / 2; },
  anticipate: x => { x = clamp01(x); const c = 1.4; return x * x * ((c + 1) * x - c); },        // pulls back, then goes
};

/** Keyframes: tween(t, [[0, 0], [0.5, 100, "snapSettle"], [1.2, 80]]) → value at t. Each key's curve shapes the move INTO it. */
export function tween(t, keys) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, v1, name = "softLand"] = keys[i], [t0, v0] = keys[i - 1];
    if (t <= t1) return lerp(v0, v1, ease[name](seg(t, t0, t1)));
  }
  return keys[keys.length - 1][1];
}

/** Enter from a scale or an edge, never from nothing: { scale, x, opacity } for an element arriving at t0. */
export function enter(t, t0, frames = 10, fps = 24, { fromScale = 1.15, fromX = 0, curve = "softLand" } = {}) {
  const k = ease[curve](seg(t, t0, t0 + frames / fps));
  return { scale: lerp(fromScale, 1, k), x: lerp(fromX, 0, k), opacity: clamp01(k * 3) };
}

/** Continuous micro-motion so no frame is dead: smooth, deterministic noise from summed sines (same seed → same path). */
export function drift(t, amp = 1, speed = 0.25, seed = 1) {
  const s = (k) => Math.sin(t * speed * k + seed * 12.9898 * k);
  return { x: amp * (0.6 * s(1.0) + 0.3 * s(2.31) + 0.1 * s(4.17)), y: amp * (0.6 * s(1.37) + 0.3 * s(2.79) + 0.1 * s(5.03)) };
}

/** Hard-cut editing: shot(t, [0, 2.5, 4, 7.25]) → { index, local } for the shot playing at t. Cut mid-motion, not on a fade. */
export function shot(t, cuts) {
  let i = 0;
  while (i + 1 < cuts.length && t >= cuts[i + 1]) i++;
  return { index: i, local: t - cuts[i] };
}

/** Snap a time to the frame grid, e.g. to land a text beat exactly on beats.json frames. */
export const onFrame = (t, fps = 24) => Math.round(t * fps) / fps;

// ---------- Cinematic motion standard (Stylist): the look stays the style's, the camera and timing follow this ----------
// Presets per style category (style.json stylist.rig). Units are relative: x/y in frame widths, zoom as a factor, rot in radians.
export const RIGS = {
  calm:      { drift: .006, push: .04, shake: .005, trans: "push-through", transS: .6 },   // documentary, paper, painting: soft drift
  editorial: { drift: .005, push: .06, shake: .006, trans: "slide",        transS: .45 },
  punchy:    { drift: .004, push: .10, shake: .010, trans: "snap zoom",    transS: .3 },   // type, games, cartoons: fast snaps
};
/** Depth layers move at different speeds against the camera: offset = camera offset × depth. */
export const LAYERS = { bg: .25, mid: 1, fg: 1.8 };

/** Closed-form damped spring 0→1 with ~10 % overshoot, settled by x = 1 (no integration: seek-safe). */
ease.spring = x => x <= 0 ? 0 : x >= 1 ? 1 : 1 - Math.exp(-6.5 * x) * Math.cos(9 * x);

/** Impact micro-shake: 4–5 frames after each hit time, decaying, seeded per frame (same t → same offset). */
export function shake(t, hits, { amp = .006, frames = 5, fps = 24, seed = 7 } = {}) {
  let x = 0, y = 0, rot = 0;
  for (const h of hits) {
    const dt = t - h, len = frames / fps, n = Math.floor(dt * fps + 1e-6);
    if (dt < 0 || n >= frames) continue;
    const d = (1 - dt / len) ** 2, r = k => Math.sin((n + 1) * 78.233 * k + seed * 12.9898);
    x += amp * d * r(1); y += amp * d * r(1.7); rot += amp * .5 * d * r(2.3);
  }
  return { x, y, rot };
}

/** Idle life for anything on screen after its entrance: breathing scale, a slow float, a slight sway. Never fully still. */
export function idle(t, seed = 1, amp = 1) {
  const d = drift(t, .004 * amp, .6, seed);
  return { x: d.x, y: d.y, scale: 1 + .008 * amp * Math.sin(t * 1.3 + seed * 2.1), rot: .004 * amp * Math.sin(t * .7 + seed * 4.7) };
}

/** Stagger: start time of the i-th element of a group, 4–6 frames apart. */
export const stagger = (t0, i, frames = 5, fps = 24) => t0 + i * frames / fps;

/** Times for a secondary micro-action (a glint, a pulse, a layer change) every ~2.75 s inside [t0, t1): refreshes attention. */
export function accents(t0, t1, every = 2.75) { const out = []; for (let t = t0 + every * .6; t < t1 - .4; t += every) out.push(+t.toFixed(3)); return out; }

/** Punch-word emphasis from its spoken time: colour mix k (0..1), a spring scale pop, an underline that draws in. */
export function emphasis(t, at, dur = .35) {
  const k = ease.softLand(seg(t, at, at + dur));
  return { k, scale: 1 + .08 * Math.max(0, ease.spring(seg(t, at, at + dur * 2)) - k), underline: ease.softLand(seg(t, at + .05, at + .05 + dur)) };
}

/** The virtual camera over a cut list: continuous drift + a slow push per shot (never linear), a camera-based move into
 *  each shot instead of a hard cut, and micro-shake on hits. rig(t, cuts, RIGS.calm, { hits, fps }) → { x, y, zoom, rot, blur }.
 *  Apply it on top of the scene's own camera; parallax comes from the depth layers. Pass { index } to evaluate a given shot,
 *  e.g. the outgoing one during a dissolve: its exit move then carries on past its end. */
export function rig(t, cuts, preset = RIGS.editorial, { hits = [], fps = 24, seed = 3, index: at } = {}) {
  const c = cam(t, cuts, preset, seed, at), p = cam(t - 1 / fps, cuts, preset, seed, at ?? shot(t, cuts).index);
  const s = shake(t, hits, { amp: preset.shake, fps, seed });
  return { ...c, x: c.x + s.x, y: c.y + s.y, rot: s.rot + .002 * Math.sin(t * .4 + seed), mb: mblur(c, p) };
}

/** Motion blur from the camera's move over the last frame (180° shutter; shake excluded so hits stay crisp):
 *  { x, y } in frame widths, 0 at rest. Use as SVG feGaussianBlur stdDeviation `${mb.x * W} ${mb.y * W}` or a canvas smear.
 *  Skip it when the style's stylist.motion.mblur is false (pixel, dither, stepped looks). */
export function mblur(c, p, { shutter = .5, cap = .012, floor = .0015 } = {}) {
  // smear length → Gaussian std dev (×0.4); below the floor (~3 px at 1920) slow pushes and drift stay sharp
  const z = Math.abs(c.zoom - p.zoom) * shutter * .5, f = v => (v *= .4, v < floor ? 0 : Math.min(cap, v));
  return { x: f(Math.abs(c.x - p.x) * shutter + z), y: f(Math.abs(c.y - p.y) * shutter + z) };
}

function cam(t, cuts, preset, seed, at) {
  const index = at ?? shot(t, cuts).index, local = t - cuts[index], end = (cuts[index + 1] ?? cuts[index] + 5) - cuts[index];
  const d = drift(t, preset.drift, .35, seed), k = seg(local, 0, end);
  let zoom = 1 + preset.push * (1 - Math.cos(Math.PI * k)) / 2, x = d.x, y = d.y, blur = 0;
  const ki = ease.softLand(seg(local, 0, preset.transS));                       // into this shot
  const ko = ease.accelExit(seg(local, end - preset.transS * .5, end + preset.transS * .5));        // out of this shot, toward the next
  if (index > 0) {
    if (preset.trans === "snap zoom") zoom *= 1 + .25 * (1 - ki);
    else if (preset.trans === "slide") x += .12 * (1 - ki);
    else { zoom *= 1 + .08 * (1 - ki); blur = 1 - ki; }                         // push-through with a focus pull
  }
  if (index + 1 < cuts.length) {
    if (preset.trans === "snap zoom") zoom *= 1 + .15 * ko;
    else if (preset.trans === "slide") x -= .08 * ko;
    else zoom *= 1 + .05 * ko;
  }
  return { x, y, zoom, blur };
}

// ---------- Kinetic type (per style: style.json stylist.motion.reveal) ----------
/** How a word or letter appears, in the style's own manner. Call per unit with its stagger start, e.g.
 *  reveal(t, stagger(t0, i), "wipe"). Returns CSS-ready values: clip (clip-path), y and tracking in em, blur in em
 *  (× font size → px), opacity, and frac (0..1: share of characters drawn, for "draw").
 *  wipe  = clip-path from left (scans, documents, data)    rise  = up from below the baseline (parent overflow:hidden)
 *  focus = blur to sharp (paint, film, craft)              track = letter-spacing closes in (type, posters)
 *  draw  = written on character by character at a steady rate (pen, chalk, terminal, light)
 *  { out: true } plays it backwards with accelExit: exits ease in, leave fast. */
export const REVEALS = ["wipe", "rise", "focus", "track", "draw"];
export function reveal(t, t0, kind = "rise", { frames = 10, fps = 24, curve = "softLand", out = false } = {}) {
  const u = seg(t, t0, t0 + frames / fps), k = out ? 1 - ease.accelExit(u) : ease[curve](u);
  const r = { clip: "none", y: 0, tracking: 0, blur: 0, opacity: 1, frac: 1 };
  if (kind === "wipe") r.clip = `inset(-10% ${((1 - k) * 100).toFixed(2)}% -10% 0)`;
  else if (kind === "rise") r.y = (1 - k) * 1.1;
  else if (kind === "focus") { r.blur = (1 - k) * .3; r.opacity = clamp01(k * 1.6); }
  else if (kind === "track") { r.tracking = (1 - k) * .45; r.opacity = clamp01(k * 2); }
  else if (kind === "draw") r.frac = out ? k : u;                                 // writing runs at a steady rate
  else throw new Error(`reveal kind ${kind}: one of ${REVEALS}`);
  return r;
}

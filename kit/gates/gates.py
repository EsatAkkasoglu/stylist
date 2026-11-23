"""Quality gates G0–G5 on a demo render, before the full film.

  python gates.py out/video.mp4 [--size 1920x1080] [--fps 24] [--dur 20] [--holds 4.0:5.5,...]
                  [--project <film folder> --lib $LEMO_OPUSCAR_HOME] [--out verify]

Run it on the PRE-MUX render (video.mjs output): mux.sh adds moving grain that hides frozen frames.
G0 render is what was asked (size, fps, length) · G2 no dead frames (> 3 identical frames outside --holds)
G3 reading time (lemo readcheck.mjs, needs --project) · G5 contact sheet + blank-frame scan.
G6 liveness (cinematic standard): near-still seconds and stretches > 3.5 s with no fresh accent, measured on lit pixels
only (dark areas are allowed to rest). Reported as LOOK with the times: compare them with the shot list.
G1 (looks like STYLE.md) and G4 (sound on picture, verify_mix.py) need your eyes: this prints what to look at.
Exit code 1 if any automatic gate fails.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path


def probe(v):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(v)],
                                  capture_output=True, text=True, check=True).stdout)
    s = j["streams"][0]; n, d = s["r_frame_rate"].split("/")
    return {"width": s["width"], "height": s["height"], "fps": float(n) / float(d), "duration": float(j["format"]["duration"])}


def g0(info, size, fps, dur):
    bad = []
    if size:
        w, h = map(int, size.lower().split("x"))
        if (info["width"], info["height"]) != (w, h): bad.append(f"size {info['width']}x{info['height']} != {size}")
    if fps and abs(info["fps"] - fps) > 0.01: bad.append(f"fps {info['fps']:.3f} != {fps}")
    if dur and abs(info["duration"] - dur) > 1 / info["fps"] + 0.05: bad.append(f"duration {info['duration']:.2f} != {dur}")
    return not bad, bad or [f"{info['width']}x{info['height']} @ {info['fps']:.3f} fps, {info['duration']:.2f} s"]


def freezes(v, fps):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(v), "-vf", f"freezedetect=n=0.001:d={3 / fps + 1e-3:.4f},metadata=mode=print:file=-",
                          "-f", "null", "-"], capture_output=True, text=True).stdout
    starts = [float(x) for x in re.findall(r"freeze_start=([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"freeze_end=([\d.]+)", log)]
    return [(s, ends[i] if i < len(ends) else None) for i, s in enumerate(starts)]


def g2(v, fps, holds):
    bad = [(s, e) for s, e in freezes(v, fps) if not any(a - 1e-3 <= s and (e is None or e <= b + 1e-3) for a, b in holds)]
    return not bad, [f"frozen from {s:.2f} s to {'end' if e is None else f'{e:.2f} s'}" for s, e in bad] or ["every frame moves (outside declared holds)"]


def g6(v, fps, holds, still=.35, gap=3.5):
    import numpy as np
    W, H = 90, 160
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(v), "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
    lit = (f[1:] > 24) | (f[:-1] > 24)
    m = (np.abs(np.diff(f, axis=0)) * lit).sum((1, 2)) / np.maximum(lit.sum((1, 2)), 1)    # motion over lit pixels, per frame
    free = lambda a, b: not any(h0 - .05 <= a and b <= h1 + .05 for h0, h1 in holds)
    n, notes, runs = int(round(fps)), [], []
    sec = np.convolve(m, np.ones(n) / n, "valid")                                            # 1 s running mean
    for i in np.flatnonzero(sec < still):                                                    # windows → merged stretches
        a, b = i / fps, (i + n) / fps
        if runs and a <= runs[-1][1]: runs[-1][1] = b
        else: runs.append([a, b])
    notes += [f"near-still {a:.1f}–{b:.1f} s" for a, b in runs if free(a, b)]
    base = np.array([np.median(m[max(0, i - 2 * n):i + 1]) for i in range(len(m))])
    hits = [i / fps for i in range(len(m)) if m[i] > max(.6, 2 * base[i])]                   # a spike = a fresh accent
    for a, b in zip([0.0] + hits, hits + [len(m) / fps]):
        if b - a > gap and free(a, b): notes.append(f"no accent {a:.1f}–{b:.1f} s ({b - a:.1f} s): add a micro-action every 2.5–3 s")
    return None, notes or ["alive: no near-still second, an accent at least every 3.5 s"]


def g3(project, lib, size=None):
    if not project:
        return None, ["skipped: pass --project and --lib to run lemo readcheck.mjs"]
    cmd = ["node", str(Path(lib) / "core" / "render" / "readcheck.mjs"), str(project)] + (["--size", size] if size else [])  # the film's frame, or vertical text reads as off-screen
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=lib)
    lines = (r.stdout + r.stderr).strip().splitlines()
    bad = [l for l in lines if l.startswith("BAD")]
    return r.returncode == 0, bad or lines[-1:]


def g5(v, info, out, n=12, holds=()):
    sheet = out / "contact_sheet.jpg"
    step = max(info["duration"] / n, 1 / info["fps"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(v), "-vf", f"fps=1/{step:.4f},scale=480:-2,tile=4x{(n + 3) // 4}",
                    "-frames:v", "1", str(sheet)], check=True)
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(v), "-vf", "blackdetect=d=0.1:pix_th=0.02", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    blanks = [(a, b) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)
              if not any(h0 - .05 <= float(a) and float(b) <= h1 + .05 for h0, h1 in holds)]   # a declared hold may be black on purpose
    msg = [f"look at {sheet}: page chrome, scrollbars, cut-off text, blank WebGL"]
    msg += [f"blank from {a} s to {b} s (lost WebGL context? or intended black)" for a, b in blanks]
    return not blanks, msg


def run(video, size=None, fps=None, dur=None, holds=(), project=None, lib=None, out="verify"):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    info = probe(video)
    res = {"G0": g0(info, size, fps, dur), "G2": g2(video, fps or info["fps"], holds), "G3": g3(project, lib, size), "G5": g5(video, info, out, holds=holds),
           "G6": g6(video, fps or info["fps"], holds),
           "G1": (None, ["your eyes: style frames vs STYLE.md, point by point"]),
           "G4": (None, ["your eyes: verify_mix.py cue frames"])}
    return {k: {"pass": v[0], "notes": v[1]} for k, v in sorted(res.items())}


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("video"); a.add_argument("--size"); a.add_argument("--fps", type=float); a.add_argument("--dur", type=float)
    a.add_argument("--holds", default=""); a.add_argument("--project"); a.add_argument("--lib"); a.add_argument("--out", default="verify")
    a = a.parse_args()
    holds = [tuple(map(float, h.split(":"))) for h in a.holds.split(",") if h]
    r = run(a.video, a.size, a.fps, a.dur, holds, a.project, a.lib, a.out)
    for k, v in r.items():
        print(f"{k} {'PASS' if v['pass'] else 'FAIL' if v['pass'] is False else 'LOOK'}: " + " | ".join(v["notes"]))
    json.dump(r, open(Path(a.out) / "gates.json", "w"), indent=1)
    sys.exit(1 if any(v["pass"] is False for v in r.values()) else 0)

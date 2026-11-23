"""Frame-locked SFX bus + music ducked under voice, in one pass.

  python mix_pro.py cue_sheet.json out_dir [--music music.wav] [--vo vo.wav] [--fps 24] [--dur seconds]

cue_sheet.json: a list of cues, one per visual event (from window.EV or your own timeline):
  {"t": 3.25 | "frame": 78, "role": "UI/CLICK", "file": "<path from search_sfx>"}           real sound
  {"t": 5.0, "role": "WHOOSH/SWISH", "synth": "whoosh", "args": {"d": 0.5}}                  fallback: lemo core/audio/sfx.py
  optional per cue: "level_db" (over the music bed; default by role), "align": "start"|"peak", "pan" (-1..1)

Writes out_dir/sfx_bus.wav, music_ducked.wav (if music), mix.wav, mix_report.json.
Then: sh $LIB/core/render/mux.sh video.mp4 out_dir/mix.wav film.mp4  (it normalises to -14 LUFS; don't do it here).
Needs ffmpeg 7+, numpy; scipy only for "synth" cues. Set LEMO_OPUSCAR_HOME for synth cues.
"""
import argparse, importlib.util, json, os, re, subprocess, sys
from pathlib import Path
import numpy as np

SR = 48000
LEVEL_DB = {"UI/CLICK": 3, "WHOOSH/SWISH": 4, "DESIGNED/RISER": 4, "DESIGNED/CHIME": 6, "IMPACT/HIT": 8}
EARLY_FRAMES = {"UI/CLICK": 1}            # clicks land one frame before the press reads as "late"
PEAK_ROLES = {"WHOOSH/SWISH"}             # whoosh: loudest point on the event frame, not its start
FMT = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"


def decode(path, rate=1.0, gain_db=0.0):
    """48 kHz stereo float. Resample first, so asetrate shifts pitch by `rate` whatever the file's own rate."""
    af = f"aresample={SR},asetrate={SR}*{rate:.4f},aresample={SR},volume={gain_db:.2f}dB"
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-af", af, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.float32).reshape(-1, 2).copy()


def write_wav(path, x):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "pcm_s24le", str(path)],
                   input=np.ascontiguousarray(x, np.float32).tobytes(), check=True)


def rms_db(x):
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-9))


def hit_db(x, win=2400):
    """Loudness of a sound as heard: RMS of its loudest 50 ms. Whole-file RMS undercounts short clicks and files with
    silent tails, and levelling by it boosted a 32 ms click to +15 dBFS."""
    e = np.square(x).mean(1)
    if len(e) <= win:
        return rms_db(x)
    c = np.cumsum(np.insert(e, 0, 0))
    return float(10 * np.log10((c[win:] - c[:-win]).max() / win + 1e-18))


def active_db(x, win=2400, below=20):
    """RMS of the parts that actually sound: 50 ms windows within `below` dB of the loudest. A VO track is mostly
    silence between lines, so its plain RMS (or mean_volume) reads ~6-10 dB low and the music ends up too loud."""
    e = np.square(x).mean(1)
    n = len(e) // win
    if n == 0:
        return rms_db(x)
    w = e[: n * win].reshape(n, win).mean(1)
    keep = w[w >= w.max() * 10 ** (-below / 10)]
    return float(10 * np.log10(keep.mean() + 1e-18))


def speech_mask(vo, win=2400):
    """Per-sample True where the voice is talking (window within 15 dB of its loudest)."""
    e = np.square(vo).mean(1)
    n = len(e) // win
    w = e[: n * win].reshape(n, win).mean(1)
    return np.repeat(w >= w.max() * 10 ** (-1.5), win)


def peak_midi(x, lo=150, hi=5000, tonal=50):
    """Main pitch of a sound as midi (fractional), or None when it is noise (peak not `tonal`× over the median)."""
    a = x.mean(1); sp = np.abs(np.fft.rfft(a * np.hanning(len(a)))); f = np.fft.rfftfreq(len(a), 1 / SR)
    m = (f > lo) & (f < hi)
    if not m.any() or sp[m].max() < tonal * np.median(sp[m]): return None
    return float(69 + 12 * np.log2(f[m][sp[m].argmax()] / 440))


def mean_volume(path):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: (-?[\d.]+) dB", out)
    return float(m.group(1)) if m else None


def synth(name, args):
    lib = os.environ.get("LEMO_OPUSCAR_HOME") or str(Path.home() / "lemo-opuscar")
    spec = importlib.util.spec_from_file_location("lemo_sfx", Path(lib) / "core" / "audio" / "sfx.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    mono = np.asarray(getattr(mod, name)(**(args or {})), np.float32)   # sfx.py renders at 48 kHz mono
    return np.stack([mono, mono], 1)


def place(cues, fps, dur, bed_db, seed=7, bed_at=None):
    """bed_at(t): the music's level around t; each sound sits over the music as it is at that moment (a click in a
    loud chorus is not lost, one in a quiet intro is not too loud). Inside a silence the film-wide bed is used."""
    rng = np.random.default_rng(seed)    # deterministic: the same cue sheet always gives the same mix
    bus = np.zeros((int(dur * SR) + SR, 2), np.float32)
    report, last_by_role = [], {}
    for i, c in enumerate(sorted(cues, key=lambda c: c.get("t", c.get("frame", 0) / fps))):
        role = c.get("role", "MISC")
        t = c["t"] if "t" in c else c["frame"] / fps
        t -= EARLY_FRAMES.get(role, 0) / fps
        src = c.get("file") or f"synth:{c.get('synth')}"
        if last_by_role.get(role) == src and "synth" not in c:
            print(f"warning: cue {i} repeats {Path(src).name} right after itself ({role}); pick another id (exclude_ids)", file=sys.stderr)
        last_by_role[role] = src
        rate, jitter = rng.uniform(0.96, 1.04), rng.uniform(-2, 2)        # micro-variation: no machine-gun repeats
        if c.get("tune_to") and c.get("file"):                             # in tune with the score: move a tonal sound's main
            pk = peak_midi(decode(c["file"]))                              # pitch to the nearest allowed pitch class (the chord at t)
            if pk is not None:
                target = min((pk + d for d in range(-6, 7)), key=lambda m: ((round(m) % 12) not in c["tune_to"], abs(m - pk)))
                rate = 2 ** ((round(target) - pk) / 12)
        rate = c.get("rate", rate)
        x = decode(c["file"], rate) if c.get("file") else synth(c["synth"], c.get("args"))
        level = c.get("level_db", LEVEL_DB.get(role, 3))
        here = bed_db if bed_at is None else max(bed_at(t), bed_db - 8)
        x *= 10 ** ((here + level + jitter - hit_db(x)) / 20)                 # loudness relative to the music bed at that moment
        pk = np.abs(x).max()
        if pk > 0.89:                                                        # one sound never clips on its own (-1 dBFS)
            x *= 0.89 / pk
        pan = float(c.get("pan", 0))
        x[:, 0] *= np.cos((pan + 1) * np.pi / 4) * 1.414; x[:, 1] *= np.sin((pan + 1) * np.pi / 4) * 1.414
        align = c.get("align", "peak" if role in PEAK_ROLES else "start")
        if align == "start":   # skip leading silence (Freesound files often open with 50–400 ms of nothing): the sound starts on t
            x = x[int(np.argmax(np.abs(x).max(1) >= np.abs(x).max() * 0.01)):]
        s = int(round(t * SR)) - (int(np.abs(x).sum(1).argmax()) if align == "peak" else 0)
        if s < 0: x, s = x[-s:], 0
        e = min(len(bus), s + len(x)); bus[s:e] += x[: e - s]
        report.append({"cue": i, "role": role, "src": src, "start_s": round(s / SR, 4), "rate": round(rate, 3),
                       "level_db_over_bed": round(level + jitter, 1), "bed_here_db": round(here, 1)})
    return bus[: int(dur * SR)], report


def mix(cue_sheet, out, music=None, vo=None, fps=24, dur=None, music_vs_vo=None):
    """music_vs_vo: where the music bed sits against the voice's speaking level, between lines (dB). Under the voice the
    sidechain takes it ~12 dB further down, so music sits ~20 dB under speech while someone talks (lemo TECHNIQUE §4:
    voice about 10 dB above the music)."""
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    cues = json.loads(Path(cue_sheet).read_text("utf8"))
    if music_vs_vo is None:   # the style's own level from score.py's report next to the music, else -10
        rp = Path(music).parent / "music_report.json" if music else None
        music_vs_vo = float(json.loads(rp.read_text("utf8")).get("duck_db", -10.0)) if rp and rp.exists() else -10.0
    if dur is None:
        lens = [float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                     capture_output=True, text=True).stdout or 0) for p in (music, vo) if p]
        last = max((c.get("t", c.get("frame", 0) / fps) for c in cues), default=0) + 2
        dur = max(lens) if lens else last   # the film's audio sets the length; pass --dur to match the picture exactly
    vo_db = active_db(decode(vo)) if vo else None
    music_gain, bed_at = 0.0, None
    if music:
        mx = decode(music); mus_db = active_db(mx)
        if vo_db is not None:
            music_gain = vo_db + music_vs_vo - mus_db           # stage the bed against the voice, not against itself
        bed_db = mus_db + music_gain
        if vo_db is None:                                     # music-led: follow the music's own arc
            bed_at = lambda t: rms_db(mx[max(0, int((t - .5) * SR)):int((t + .5) * SR)]) + music_gain
    else:
        bed_db = (vo_db + music_vs_vo) if vo_db is not None else -30.0   # no music: SFX still sit under the voice
    bus, report = place(cues, fps, dur, bed_db, bed_at=bed_at)
    if np.abs(bus).max() > 1:
        print(f"note: SFX bus peaks at {20*np.log10(np.abs(bus).max()):.1f} dBFS before the mix; mux.sh's limiter will catch it", file=sys.stderr)
    write_wav(out / "sfx_bus.wav", bus)

    ins, graph, outs, th = [], [], [], None
    if music:
        ins += ["-i", str(music)]; graph.append(f"[{len(ins)//2-1}:a]{FMT},volume={music_gain:.2f}dB[mus]")
    if vo:
        ins += ["-i", str(vo)]; graph.append(f"[{len(ins)//2-1}:a]{FMT},asplit=2[sc][vox]")
    ins += ["-i", str(out / "sfx_bus.wav")]; graph.append(f"[{len(ins)//2-1}:a]{FMT}[fx]")
    if music and vo:
        th = 10 ** ((vo_db - 15) / 20)   # measured, not guessed: a fixed 0.08 doesn't duck a -26 dB voice at all
        graph.append(f"[mus][sc]sidechaincompress=threshold={th:.5f}:ratio=6:attack=15:release=350,asplit=2[duck][duckout]")
        outs, parts = ["-map", "[duckout]", "-c:a", "pcm_s24le", str(out / "music_ducked.wav")], ["[duck]", "[vox]", "[fx]"]
    else:
        parts = (["[mus]"] if music else []) + (["[vox]"] if vo else []) + ["[fx]"]
        if vo: graph[-2] = graph[-2].replace(",asplit=2[sc][vox]", "[vox]")
    graph.append(f"{''.join(parts)}amix=inputs={len(parts)}:duration=longest:normalize=0,atrim=0:{dur:.3f}[out]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(graph),
                    "-map", "[out]", "-c:a", "pcm_s24le", str(out / "mix.wav"), *outs], check=True)
    rep = {"duration_s": round(dur, 3), "music_bed_db": round(bed_db, 1), "music_gain_db": round(music_gain, 1),
           "vo_active_db": None if vo_db is None else round(vo_db, 1), "music_vs_vo_target_db": music_vs_vo,
           "duck_threshold": th, "cues": report}
    if music and vo:   # measure what was actually made, so a bad balance shows up in the report and in tests
        md, v = decode(out / "music_ducked.wav"), decode(vo)
        n = min(len(md), len(v)); m = speech_mask(v[:n]); n = len(m); md, v = md[:n], v[:n]
        quiet = ~m & (np.abs(md).sum(1) > 1e-4)
        rep["measured"] = {"music_under_speech_db": round(rms_db(md[m]) - rms_db(v[m]), 1) if m.any() else None,
                           "music_between_lines_db": round(rms_db(md[quiet]) - vo_db, 1) if quiet.any() else None}
    (out / "mix_report.json").write_text(json.dumps(rep, indent=1), "utf8")
    return rep


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("cue_sheet"); a.add_argument("out_dir")
    a.add_argument("--music"); a.add_argument("--vo"); a.add_argument("--fps", type=float, default=24); a.add_argument("--dur", type=float)
    a.add_argument("--music-vs-vo", type=float, help="music bed vs speaking level between lines, dB (default: duck_db from music_report.json, else -10)")
    a = a.parse_args()
    r = mix(a.cue_sheet, a.out_dir, a.music, a.vo, a.fps, a.dur, a.music_vs_vo)
    print(f"{len(r['cues'])} cues -> {Path(a.out_dir) / 'mix.wav'}  {r.get('measured', '')}")

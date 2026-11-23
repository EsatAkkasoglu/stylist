"""Music written as notes: a note list (JSON) -> MusicXML + MIDI -> audio, headless (runs on a server).

  python notes.py cue.json out_dir [--space hall|dry] [--engine auto|fluidsynth|musescore]
  python notes.py score.musicxml out_dir      # or score.mid: render an existing score

cue.json:
  {"title": "Art Deco Cue", "bpm": 150, "time": "4/4",
   "tempos": [[16, 120]],                                   # optional tempo changes: [beat, bpm]
   "parts": [{"name": "Clarinet", "program": 71,            # General MIDI program (0 piano, 32 ac. bass, 56 trumpet,
              "notes": [["D5", 1, 70], ["F5", 1], [null, 2], # 59 muted trumpet, 71 clarinet, 105 banjo, 11 vibraphone ...)
                        [["Bb2", "D4", "F4"], 1, 90]]}]}     # [pitch | [chord] | null, beats, velocity?]
Every part must total the same number of beats (whole bars). Write the tune by hand: a motif, its answer,
a turn to the climax; one chord per bar under it. Pitches are concert pitch.

Writes out_dir/score.musicxml (opens in MuseScore), score.mid, music.wav (48 kHz, peak -1 dBFS).
Then use music.wav as `--music` in mix_pro.py like a score.py render.

Server install (Debian/Ubuntu): sh kit/setup_server.sh. Sound comes from FluidSynth + the MuseScore General
soundfont (MIT): the same samples MuseScore itself plays. If FluidSynth is missing, MuseScore's CLI
(mscore / mscore3 / MuseScore4) renders instead. Set STYLIST_SOUNDFONT to use another .sf2/.sf3.
Needs: music21, numpy, soundfile, pedalboard.
"""
import argparse, glob, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

SR = 48000
SOUNDFONTS = ["/usr/share/sounds/sf3/MuseScore_General*.sf3", "/usr/share/sounds/sf2/*.sf2", "/usr/share/soundfonts/*.sf[23]",
              "C:/Program Files/MuseScore 4/sound/*.sf3", "/Applications/MuseScore 4.app/Contents/Resources/sound/*.sf3"]
MUSESCORE = ["mscore", "mscore3", "mscore4portable", "musescore", "MuseScore4",
             "C:/Program Files/MuseScore 4/bin/MuseScore4.exe", "/Applications/MuseScore 4.app/Contents/MacOS/mscore"]


def score_from(spec):
    from music21 import stream, note, chord, meter, tempo, instrument, pitch, metadata
    p21 = lambda t: pitch.Pitch(midi=t) if isinstance(t, int) else pitch.Pitch(t.replace("b", "-") if len(t) > 1 and t[1] == "b" else t)
    lens = {p["name"]: sum(e[1] for e in p["notes"]) for p in spec["parts"]}
    if len(set(round(v, 6) for v in lens.values())) != 1:
        raise SystemExit(f"parts differ in length (beats): {lens}; pad the short ones with rests")
    sc = stream.Score(); sc.metadata = metadata.Metadata(title=spec.get("title", "Cue"), composer="Stylist")
    for i, p in enumerate(spec["parts"]):
        part = stream.Part(); part.id = p["name"]
        ins = instrument.instrumentFromMidiProgram(p.get("program", 0)); ins.partName = p["name"]; ins.midiProgram = p.get("program", 0)
        part.insert(0, ins); part.insert(0, meter.TimeSignature(spec.get("time", "4/4")))
        for e in p["notes"]:
            t, beats, vel = e[0], e[1], (e[2] if len(e) > 2 else 72)
            x = note.Rest(quarterLength=beats) if t is None else chord.Chord([p21(v) for v in t], quarterLength=beats) if isinstance(t, list) \
                else note.Note(p21(t), quarterLength=beats)
            if t is not None: x.volume.velocity = vel
            part.append(x)
        if i == 0:   # tempo marks after the notes, or makeMeasures shifts them
            for b, bpm in [[0, spec.get("bpm", 120)]] + spec.get("tempos", []):
                part.insert(float(b), tempo.MetronomeMark(number=bpm))
        part.makeMeasures(inPlace=True); sc.insert(0, part)
    return sc


def find(patterns):
    for p in patterns:
        hit = shutil.which(p) or next(iter(sorted(glob.glob(p))), None)
        if hit: return hit


def render(mid, wav, engine="auto"):
    sfont = os.environ.get("STYLIST_SOUNDFONT") or find(SOUNDFONTS)
    fs = shutil.which("fluidsynth")
    if engine in ("auto", "fluidsynth") and fs and sfont:
        subprocess.run([fs, "-ni", "-q", "-g", "0.5", "-r", str(SR), "-F", str(wav), sfont, str(mid)], check=True)
        return f"fluidsynth + {Path(sfont).name}"
    ms = find(MUSESCORE)
    if engine in ("auto", "musescore") and ms:
        env = os.environ if os.name == "nt" else {**os.environ, "QT_QPA_PLATFORM": "offscreen"}   # headless Linux has no display
        subprocess.run([ms, "-o", str(Path(wav).resolve()), str(Path(mid).resolve())], check=True, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return Path(ms).name
    raise SystemExit("no renderer: install FluidSynth + a soundfont (sh kit/setup_server.sh) or MuseScore")


def master(raw, out, space):
    x, sr = sf.read(raw, dtype="float32", always_2d=True)
    nz = np.flatnonzero(np.abs(x).max(1) > 1e-4)
    x = x[: (nz[-1] + int(0.3 * sr)) if len(nz) else len(x)]          # drop the renderer's silent tail, keep the ring
    if space == "hall":   # 1930s hall: no sub, soft top, a little glue and tape, shared room
        import pedalboard as pb
        x = pb.Pedalboard([pb.HighpassFilter(70), pb.LowpassFilter(9500), pb.Compressor(threshold_db=-18, ratio=2, attack_ms=15, release_ms=180),
                           pb.Distortion(drive_db=3), pb.Reverb(room_size=0.55, damping=0.6, wet_level=0.18, dry_level=0.85, width=0.8)])(x.T.copy(), sr).T
    f = min(len(x), int(0.4 * sr)); x[-f:] *= np.linspace(1, 0, f)[:, None]
    x *= 10 ** (-1 / 20) / (np.abs(x).max() + 1e-9)
    sf.write(out, x, sr, subtype="PCM_24")


def main(src, out_dir, space="hall", engine="auto"):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    src = Path(src)
    if src.suffix == ".json":
        sc = score_from(json.loads(src.read_text("utf8")))
        sc.write("musicxml", fp=out / "score.musicxml"); sc.write("midi", fp=out / "score.mid"); mid = out / "score.mid"
    elif src.suffix in (".mid", ".midi"):
        mid = src
    else:
        from music21 import converter
        mid = out / "score.mid"; converter.parse(str(src)).write("midi", fp=mid)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        how = render(mid, raw, engine)
        master(raw, out / "music.wav", space)
    print(f"{how} -> {out / 'music.wav'} ({sf.info(out / 'music.wav').duration:.1f} s)")


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("src"); a.add_argument("out_dir")
    a.add_argument("--space", default="hall", choices=["hall", "dry"]); a.add_argument("--engine", default="auto", choices=["auto", "fluidsynth", "musescore"])
    a = a.parse_args(); main(a.src, a.out_dir, a.space, a.engine)

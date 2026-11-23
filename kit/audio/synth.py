"""Electronic score: a note list played by Surge XT factory patches inside DawDreamer, headless (runs on a server).
For synthwave / HUD / dataviz / chiptune-ish styles; acoustic and orchestral styles use notes.py.

  python synth.py cue.json out_dir [--space neon|dry]

cue.json (same note format as notes.py, but each part names a Surge patch instead of a GM program):
  {"title": "HUD Cue", "bpm": 112,
   "parts": [{"name": "Pad", "patch": "Polysynths/Juno-60 Strings", "gain_db": -6,
              "notes": [[["A3", "C4", "E4"], 4, 70], [null, 4], ...]}],       # [pitch | [chord] | null, beats, velocity?]
   "mutes": [[39, 40]]}                     # optional [from_beat, to_beat]: whole mix cut to digital silence (tails too)
Patches: <category>/<name> from Surge's patches_factory (Basses, Leads, Pads, Plucks, Polysynths, Percussion, Sequences ...);
`python synth.py --list Leads` prints them. Each part totals the same number of beats.

Writes out_dir/music.wav (48 kHz, peak -1 dBFS) and out_dir/stems/<part>.wav; use music.wav as `--music` in mix_pro.py.

Server install (Debian/Ubuntu): sh kit/setup_server.sh (WITH_SURGE=1). Needs dawdreamer, numpy, soundfile, pedalboard.
Set STYLIST_SURGE (path to "Surge XT.vst3") and STYLIST_SURGE_PATCHES if Surge lives somewhere else.
"""
import argparse, glob, os, re, struct, sys, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

SR = 48000
VST = ["/usr/lib/vst3/Surge XT.vst3", "/usr/local/lib/vst3/Surge XT.vst3", "~/.vst3/Surge XT.vst3",
       "C:/Program Files/Common Files/VST3/Surge XT.vst3", "/Library/Audio/Plug-Ins/VST3/Surge XT.vst3"]
PATCHES = ["/usr/share/surge-xt/patches_factory", "/usr/local/share/surge-xt/patches_factory", "~/.local/share/surge-xt/patches_factory",
           "C:/ProgramData/Surge XT/patches_factory", "/Library/Application Support/Surge XT/patches_factory"]
B64 = ".ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+"   # JUCE MemoryBlock base64 alphabet


def first(env, paths):
    for p in [os.environ.get(env)] + paths:
        if p and Path(os.path.expanduser(p)).exists(): return os.path.expanduser(p)
    raise SystemExit(f"Surge XT not found ({env}); install it: WITH_SURGE=1 sh kit/setup_server.sh")


def midi(t):
    m = re.fullmatch(r"([A-G])([#b]?)(-?\d)", t)
    return 12 * (int(m[3]) + 1) + "C D EF G A B".index(m[1]) + {"#": 1, "b": -1, "": 0}[m[2]]


def patch_state(fxp):
    """A Surge .fxp patch as the VST3 state DawDreamer's load_state expects: the fxp chunk ('sub3' ...) base64'd into
    JUCE's <VST3PluginState><IComponent>, behind the 'VC2!' + length header."""
    chunk = Path(fxp).read_bytes()[60:]                     # 60-byte fxp header, then Surge's own patch chunk
    v = int.from_bytes(chunk, "little")
    enc = "".join(B64[(v >> (6 * i)) & 63] for i in range((len(chunk) * 8 + 5) // 6))
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<VST3PluginState><IComponent>{len(chunk)}.{enc}</IComponent></VST3PluginState>'.encode()
    return b"VC2!" + struct.pack("<I", len(xml)) + xml + b"\0"


def render(spec, out, space):
    import dawdreamer as daw
    vst, pdir = first("STYLIST_SURGE", VST), first("STYLIST_SURGE_PATCHES", PATCHES)
    beat = 60.0 / spec["bpm"]
    lens = {p["name"]: sum(e[1] for e in p["notes"]) for p in spec["parts"]}
    if len(set(round(v, 6) for v in lens.values())) != 1:
        raise SystemExit(f"parts differ in length (beats): {lens}; pad the short ones with rests")
    dur = max(lens.values()) * beat + 3.0                    # + tail for releases and the patches' own reverb
    (out / "stems").mkdir(parents=True, exist_ok=True)
    mix = None
    for p in spec["parts"]:
        eng = daw.RenderEngine(SR, 512); eng.set_bpm(spec["bpm"])
        syn = eng.make_plugin_processor("syn", vst)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".state") as f:
            f.write(patch_state(Path(pdir) / f"{p['patch']}.fxp"))
        syn.load_state(f.name); os.unlink(f.name)
        eng.load_graph([(syn, [])]); eng.render(0.2)          # Surge swaps the patch in on the audio thread: prime one block first
        t = 0.0
        for e in p["notes"]:
            if e[0] is not None:
                for n in (e[0] if isinstance(e[0], list) else [e[0]]):
                    syn.add_midi_note(midi(n), int(e[2] if len(e) > 2 else 90), t * beat, e[1] * beat * p.get("legato", 0.95))
            t += e[1]
        eng.load_graph([(syn, [])]); eng.render(dur)
        a = eng.get_audio().T * 10 ** (p.get("gain_db", 0) / 20)
        sf.write(out / "stems" / f"{p['name']}.wav", a.astype(np.float32), SR)
        mix = a if mix is None else mix + a
    if space == "neon":   # glue, a wide room and a little tape: one space for every synth
        import pedalboard as pb
        mix = pb.Pedalboard([pb.HighpassFilter(30), pb.Compressor(threshold_db=-16, ratio=2.5, attack_ms=10, release_ms=150),
                             pb.Distortion(drive_db=2), pb.Reverb(room_size=0.6, damping=0.5, wet_level=0.12, dry_level=0.9, width=1.0)])(
            np.ascontiguousarray(mix.T, np.float32), SR).T
    for b0, b1 in spec.get("mutes", []):   # true digital silence: patch releases, delays and the room tail are cut too
        i0, i1, f = int(b0 * beat * SR), int(b1 * beat * SR), int(0.012 * SR)
        mix[i0 - f:i0] *= np.linspace(1, 0, f)[:, None]; mix[i0:i1] = 0
    nz = np.flatnonzero(np.abs(mix).max(1) > 1e-4); mix = mix[: nz[-1] + 1] if len(nz) else mix
    f = min(len(mix), int(0.3 * SR)); mix[-f:] *= np.linspace(1, 0, f)[:, None]
    mix *= 10 ** (-1 / 20) / (np.abs(mix).max() + 1e-9)
    sf.write(out / "music.wav", mix.astype(np.float32), SR, subtype="PCM_24")
    return len(mix) / SR


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--list":
        print("\n".join(sorted(Path(x).stem for x in glob.glob(str(Path(first("STYLIST_SURGE_PATCHES", PATCHES)) / sys.argv[2] / "*.fxp"))))); sys.exit()
    a = argparse.ArgumentParser(); a.add_argument("cue"); a.add_argument("out_dir"); a.add_argument("--space", default="neon", choices=["neon", "dry"])
    a = a.parse_args()
    import json
    secs = render(json.loads(Path(a.cue).read_text("utf8")), Path(a.out_dir), a.space)
    print(f"surge xt -> {Path(a.out_dir) / 'music.wav'} ({secs:.1f} s)")

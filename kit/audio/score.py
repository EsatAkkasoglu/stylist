"""Original, picture-locked score in the style's own instruments: real samples (lemo sampler), physically modelled plucks
and synth voices, arranged from the film's sections, then measured and critiqued.

  python score.py plan.json out_dir      # needs LEMO_OPUSCAR_HOME (default ~/lemo-opuscar), numpy, scipy, soundfile; numba for pluck:*

plan.json:
  {"genre": "future-pop", "dur": 45,
   "ensemble": {...},                      # the style's band: copy style.json stylist.score (get_style), or "style": "path/style.json"
   "mood": "bright",                       # the TOPIC: bright | warm | playful | tense | dark | wonder | epic | calm
   "sections": [{"t": 0, "energy": 0.3}, {"t": 7.5, "energy": 0.7}, {"t": 39, "energy": 1.0}],
   "hits": [39.0], "silences": [[38.5, 39.0]], "end": "ring",          # ring | button
   "bpm": 120, "key": "A", "mode": "major", "seed": 1}                 # explicit keys win over mood, ensemble and genre
Order of precedence: genre < style ensemble < topic mood < explicit plan keys.
Section starts snap to the nearest beat (cut the picture on the grid: out_dir/music_report.json "beats").
Energy 0..1 decides what plays (pad < bass < pulse < drums < lead). A rise gets a riser and a drum fill into the section,
every section start an impact, `hits` a big hit at the exact picture time (not snapped), `silences` true silence.

Writing rules built in (GitHub research, guide "music"): one motif per film, stated / sequenced on the chord / repeated /
answered with a cadence in 4-bar phrases, an octave higher at the climax; strong-beat melody notes snap to chord tones;
chords move by the nearest voicing (no root-position jumps); velocity accents and micro-timing per genre (0 for chiptune);
fills at section seams; a lead and a counter voice trade bars and merge at the peak.

Writes out_dir/music.wav, out_dir/stems/<layer>.wav and out_dir/music_report.json (beat grid, sections, credits, critique).
The critique lists measured problems (flat arc, missing climax, hook too rare or late, monotone melody, an instrument the
style forbids, dull or boomy balance) with a fix each: fix the plan or the section and render again until it is empty.
"""
import json, os, sys, zlib
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

LIB = Path(os.environ.get("LEMO_OPUSCAR_HOME") or Path.home() / "lemo-opuscar")
sys.path.insert(0, str(LIB))
from core.audio import sampler as S          # noqa: E402  (real instruments, CC0 / CC BY)
from core.audio.sfx import SR, limit         # noqa: E402
try:
    from core.audio import pluck as P        # noqa: E402  (guqin, koto, shamisen, pipa…; needs numba)
except Exception:                            # ponytail: pluck:* voices fall back to harp samples without numba
    P = None

NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
MODES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10],
         "mixolydian": [0, 2, 4, 5, 7, 9, 10], "lydian": [0, 2, 4, 6, 7, 9, 11], "phrygian": [0, 1, 3, 5, 7, 8, 10],
         "pentatonic": [0, 2, 4, 7, 9], "minor_pentatonic": [0, 3, 5, 7, 10], "in": [0, 1, 5, 7, 8], "yo": [0, 2, 5, 7, 9]}

# The topic's feeling: mode, tempo shift, progression. A style keeps its instruments whatever the mood.
# Where the band is heard (ensemble "space"): sets reverb (size, wet), band limits (Hz) and tape drive (0..1); explicit ensemble keys still win.
SPACES = {
    "dry":          dict(reverb=(0.15, 0.04)),
    "small-room":   dict(reverb=(0.25, 0.12)),
    "vintage-hall": dict(reverb=(0.75, 0.30), lowpass=9000, highpass=90, tape=0.3),    # 1930s ballroom, warm tape
    "tape":         dict(lowpass=12000, tape=0.4),
    "speaker":      dict(reverb=(0.2, 0.08), lowpass=3500, highpass=300, tape=0.5),    # radio / PA / old TV
    "cathedral":    dict(reverb=(0.95, 0.40)),
}
# How far the music bed sits under the voice, between lines (dB; mix_pro reads it from music_report.json). Busy bands sit lower.
DUCK = {"hot-jazz": -13.0, "rock-opening": -13.0, "future-pop": -12.0, "city-pop": -12.0, "cinematic-pulse": -12.0, "synthwave": -12.0,
        "chiptune": -12.0, "chamber-march": -12.0, "drone-sparse": -8.0, "ambient-wonder": -8.0}

MOODS = {
    "bright":  dict(mode="major", bpm=+4, prog=[1, 5, 6, 4]),
    "playful": dict(mode="major", bpm=+8, prog=[1, 4, 5, 4]),
    "warm":    dict(mode="major", bpm=-6, prog=[1, 6, 4, 5], sevenths=True),
    "calm":    dict(mode="major", bpm=-12, prog=[1, 4, 1, 5]),
    "wonder":  dict(mode="lydian", bpm=-8, prog=[1, 2, 6, 5]),
    "tense":   dict(mode="minor", bpm=+0, prog=[1, 6, 7, 5]),
    "dark":    dict(mode="minor", bpm=-10, prog=[1, 6, 4, 5]),
    "epic":    dict(mode="minor", bpm=+2, prog=[1, 6, 3, 7]),
}

# Each genre is data: the groove backbone. Drum patterns are 16 steps per bar ("x" hit, "o" soft hit, "." rest);
# min = the energy at which a layer joins; jitter_ms = human timing spread (0 = machine-tight on purpose).
GENRES = {
    "cinematic-pulse": dict(           # modern tech / trailer: synth ostinato, real strings and kit, big hits
        bpm=112, key="D", mode="minor", prog=[1, 6, 3, 7], swing=0.0, reverb=(0.55, 0.22), jitter_ms=5,
        pad=dict(kind="strings", min=0.0), bass=dict(kind="synth", pattern="x.......x.......", min=0.25),
        pulse=dict(pattern="xxxxxxxxxxxxxxxx", min=0.35, cutoff=(500, 5200)),
        drums=dict(kick=("drum_kit", "kick_drum_left", "x.....x...x.....", 0.6), snare=("drum_kit", "snare_1", "........x.......", 0.7),
                   hat=("hihat", "closed", "..x...x...x...x.", 0.5), perc=("toms", "low", "............o.o.", 0.8)),
        lead=dict(inst="piano", octave=5, motif=[0, 2, 4, 2, 7, 4], rhythm=[0, 2, 4, 6, 8, 12], min=0.75, vel=0.55),
        sidechain=0.45, impact="cinematic"),
    "future-pop": dict(                # bright, optimistic product launch: four on the floor, pumping supersaws, claps
        bpm=122, key="A", mode="major", prog=[6, 4, 1, 5], swing=0.0, reverb=(0.4, 0.15), jitter_ms=4,
        pad=dict(kind="supersaw", min=0.0), bass=dict(kind="synth", pattern="..x...x...x...x.", min=0.3),
        pulse=dict(pattern="x.x.x.x.x.x.x.x.", min=0.5, cutoff=(900, 7000)),
        drums=dict(kick=("drum_kit", "kick_drum_left", "x...x...x...x...", 0.6), snare=("claps", "group", "....x.......x...", 0.65),
                   hat=("drum_kit", "hi_hat_open", "..x...x...x...x.", 0.5), perc=("shaker", "down", "xxxxxxxxxxxxxxxx", 0.8)),
        lead=dict(inst="pluck", octave=5, motif=[4, 2, 0, 2, 4, 4, 4], rhythm=[0, 2, 4, 6, 8, 10, 12], min=0.7, vel=0.6),
        sidechain=0.65, impact="clean"),
    "lofi-chill": dict(                # warm, human, handmade: swung piano 7ths, dusty kit, vinyl
        bpm=80, key="F", mode="major", prog=[2, 5, 1, 6], swing=0.62, reverb=(0.35, 0.18), sevenths=True, jitter_ms=12, laid_back_ms=14,
        pad=dict(kind="comp", inst="piano", min=0.0), bass=dict(kind="sample", inst="jazz_bass", pattern="x.....x...x.....", min=0.2),
        pulse=None,
        drums=dict(kick=("drum_kit", "kick_drum_left", "x.........x.....", 0.45), snare=("snare2", "on", "....x.......x...", 0.5),
                   hat=("hihat", "closed", "x.x.x.x.x.x.x.x.", 0.35), perc=("shaker", "down", "..x...x...x...x.", 0.7)),
        lead=dict(inst="vibraphone", octave=5, motif=[4, 2, 0, 1], rhythm=[0, 3, 6, 10], min=0.65, vel=0.45),
        sidechain=0.0, impact="soft", crackle=True, lowpass=7500),
    "synthwave": dict(                 # retro-future neon: saw arps, octave bass, gated snare
        bpm=100, key="E", mode="minor", prog=[1, 6, 7, 4], swing=0.0, reverb=(0.6, 0.25), jitter_ms=0,
        pad=dict(kind="supersaw", min=0.0), bass=dict(kind="synth", pattern="xxxxxxxxxxxxxxxx", octaves=True, min=0.3),
        pulse=dict(pattern="x.xxx.xxx.xxx.xx", min=0.45, cutoff=(700, 6000), arp=True),
        drums=dict(kick=("drum_kit", "kick_drum_left", "x.......x.......", 0.55), snare=("drum_kit", "snare_2", "....x.......x...", 0.6),
                   hat=("hihat", "closed", "x.x.x.x.x.x.x.x.", 0.5), perc=("toms", "high", "..............oo", 0.85)),
        lead=dict(inst="saw", octave=5, motif=[0, 4, 7, 9, 7, 4], rhythm=[0, 2, 4, 8, 10, 12], min=0.75, vel=0.5),
        sidechain=0.35, impact="cinematic", gated_snare=True),
    "ambient-wonder": dict(            # awe, nature, science wonder: felt piano, strings swells, chimes, no kit
        bpm=72, key="C", mode="major", prog=[1, 5, 6, 4], swing=0.0, reverb=(0.85, 0.35), jitter_ms=10,
        pad=dict(kind="strings", min=0.0), bass=dict(kind="synth", pattern="x...............", min=0.3),
        pulse=dict(pattern="x..x..x.x..x..x.", min=0.55, cutoff=(400, 2600), soft=True),
        drums=dict(kick=("bass_drum", None, "x...............", 0.75), snare=None, hat=("shaker", "down", "..x...x...x...x.", 0.6), perc=None),
        lead=dict(inst="piano", octave=5, motif=[4, 2, 4, 7, 6, 4], rhythm=[0, 3, 6, 8, 11, 14], min=0.45, vel=0.4, sparkle="hand_chimes"),
        sidechain=0.0, impact="soft"),
    # ---- backbones for the styles' own idioms (STYLE.md sound palettes) ----
    "chiptune": dict(                  # 8/16-bit: two pulse voices, triangle bass, noise drums, SNES echo; max 4 voices
        bpm=140, key="C", mode="major", prog=[1, 6, 4, 5], swing=0.0, reverb=(0.2, 0.05), jitter_ms=0, echo=(0.27, 0.35),
        pad=dict(kind="arp", inst="pulse25", min=0.0), bass=dict(kind="synth", inst="triangle", pattern="x.x.x.x.x.x.x.x.", min=0.2),
        pulse=None,
        drums=dict(kick=("chip", "kick", "x.......x.......", 0.45), snare=("chip", "snare", "....x.......x...", 0.5),
                   hat=("chip", "hat", "x.x.x.x.x.x.x.x.", 0.55), perc=None),
        lead=dict(inst="square", octave=5, motif=[0, 2, 4, 7, 4, 5, 4], rhythm=[0, 2, 4, 6, 8, 10, 12], min=0.3, vel=0.6),
        sidechain=0.0, impact="clean"),
    "jazz-combo": dict(                # West-Coast cool / spy / lounge: walking bass, brushes on the ride, vibes comp
        bpm=132, key="F", mode="dorian", prog=[2, 5, 1, 6], swing=0.64, reverb=(0.35, 0.16), sevenths=True, jitter_ms=10, laid_back_ms=15,
        pad=dict(kind="comp", inst="vibraphone", pattern="..x.....x..x....", min=0.0), bass=dict(kind="sample", inst="jazz_bass", walk=True, min=0.15),
        pulse=None,
        drums=dict(kick=("drum_kit", "kick_drum_left", "x...............", 0.7), snare=("snare2", "taps", ".......o.......o", 0.4),
                   hat=("drum_kit", "ride_left", "x...x.x.x...x.x.", 0.3), perc=("hihat", "pedal", "....x.......x...", 0.45)),
        lead=dict(inst="flute", octave=5, motif=[4, 6, 7, 4, 2, 0], rhythm=[0, 2, 3, 6, 8, 12], min=0.5, vel=0.5),
        sidechain=0.0, impact="soft"),
    "hot-jazz": dict(                  # 1920s–30s dance band / ragtime / newsreel: oom-pah tuba, banjo on 2 & 4
        bpm=176, key="Bb", mode="major", prog=[1, 6, 2, 5], swing=0.58, reverb=(0.3, 0.12), jitter_ms=9,
        pad=dict(kind="comp", inst="honky_tonk", pattern="....x.......x...", min=0.0), bass=dict(kind="sample", inst="tuba_stac", pattern="x.......x.......", min=0.0),
        pulse=dict(kind="comp", inst="strumstick", pattern="....x.......x...", min=0.3),
        drums=dict(kick=None, snare=("snare2", "taps", "....x.......x...", 0.4), hat=("woodblock", "a", "..x...x...x...x.", 0.6), perc=("snare2", "roll", "..............x.", 0.85)),
        lead=dict(inst="trumpet", octave=5, motif=[0, 2, 4, 5, 4, 2, 0], rhythm=[0, 2, 3, 4, 6, 8, 10], min=0.45, vel=0.55),
        sidechain=0.0, impact="soft"),
    "minimal-pulse": dict(             # Reich grammar: interlocking mallet ostinati added one by one, no kit
        bpm=112, key="D", mode="major", prog=[1, 4, 6, 5], swing=0.0, reverb=(0.4, 0.2), jitter_ms=4,
        pad=dict(kind="arp", inst="marimba", min=0.0), bass=dict(kind="sample", inst="contrabass_pizz", pattern="x.......x.......", min=0.3),
        pulse=dict(kind="arp", inst="glockenspiel", pattern="x..x..x.x..x..x.", min=0.55),
        drums=dict(kick=None, snare=None, hat=("shaker", "down", "x.x.x.x.x.x.x.x.", 0.6), perc=("woodblock", "b", "x..x..x...x..x..", 0.75)),
        lead=dict(inst="vibraphone", octave=5, motif=[0, 4, 2, 5, 4], rhythm=[0, 3, 6, 8, 12], min=0.4, vel=0.5),
        sidechain=0.0, impact="soft"),
    "folk-acoustic": dict(             # hand-played: strummed guitar, upright bass, cajon, harmonica / fiddle
        bpm=104, key="G", mode="major", prog=[1, 5, 6, 4], swing=0.0, reverb=(0.35, 0.16), jitter_ms=11,
        pad=dict(kind="comp", inst="pluck:acoustic_guitar", pattern="x..x..x...x.x...", min=0.0), bass=dict(kind="sample", inst="jazz_bass", pattern="x.......x.......", min=0.25),
        pulse=None,
        drums=dict(kick=("cajon", "bass", "x.......x.......", 0.5), snare=("cajon", "slap", "....x.......x...", 0.55),
                   hat=("shaker", "down", "x.x.x.x.x.x.x.x.", 0.4), perc=("tambourine", None, "....x.......x...", 0.8)),
        lead=dict(inst="harmonica", octave=5, motif=[4, 2, 0, 2, 4, 5, 4], rhythm=[0, 2, 4, 6, 8, 9, 10], min=0.5, vel=0.5),
        sidechain=0.0, impact="soft"),
    "chamber-march": dict(             # production line / Soviet montage / music hall: staccato ostinato, snare, low brass
        bpm=120, key="D", mode="minor", prog=[1, 4, 5, 1], swing=0.0, reverb=(0.35, 0.15), jitter_ms=5,
        pad=dict(kind="arp", inst="cellos_spic", min=0.0), bass=dict(kind="sample", inst="tuba_stac", pattern="x...x...x...x...", min=0.2),
        pulse=dict(kind="arp", inst="bassoon_stac", pattern="x.x.x.x.x.x.x.x.", min=0.4),
        drums=dict(kick=("bass_drum", None, "x.......x.......", 0.55), snare=("snare", "on", "..x.x.x...x.x.x.", 0.5),
                   hat=("woodblock", "a", "x...x...x...x...", 0.35), perc=("timpani", "drum2", "x...............", 0.85)),
        lead=dict(inst="xylophone", octave=5, motif=[0, 0, 2, 0, 4, 0, 1, 2], rhythm=[0, 2, 4, 6, 8, 10, 12, 14], min=0.6, vel=0.55),
        sidechain=0.0, impact="cinematic"),
    "baroque-motor": dict(             # blueprint / clockwork: harpsichord 16ths, imitative lines, pizzicato bass
        bpm=96, key="G", mode="minor", prog=[1, 4, 5, 1], swing=0.0, reverb=(0.4, 0.18), jitter_ms=3,
        pad=dict(kind="arp", inst="harpsichord", min=0.0), bass=dict(kind="sample", inst="contrabass_pizz", pattern="x...x...x...x...", min=0.5),
        pulse=None,
        drums=dict(kick=None, snare=None, hat=("woodblock", "c", "x...x...x...x...", 0.7), perc=("timpani", "drum3", "x...............", 0.9)),
        lead=dict(inst="bassoon", octave=4, motif=[0, 1, 2, 4, 3, 2, 1], rhythm=[0, 2, 4, 6, 8, 10, 12], min=0.45, vel=0.5, canon=True),
        sidechain=0.0, impact="soft"),
    "east-asian": dict(                # pentatonic plucked lead, flute line, frame drum / taiko, space
        bpm=84, key="D", mode="pentatonic", prog=[1, 4, 2, 5], swing=0.0, reverb=(0.6, 0.25), jitter_ms=12,
        pad=dict(kind="drone", inst="cellos", min=0.0), bass=None,
        pulse=dict(kind="arp", inst="pluck:koto", pattern="x..x..x.x.......", min=0.4),
        drums=dict(kick=("frame_drum", "large", "x.......x.....x.", 0.5), snare=None, hat=("woodblock", "c", "....x.......x...", 0.65), perc=("bass_drum", None, "x...............", 0.85)),
        lead=dict(inst="flute", octave=5, motif=[0, 1, 2, 4, 2], rhythm=[0, 4, 6, 8, 12], min=0.3, vel=0.45),
        sidechain=0.0, impact="soft"),
    "drone-sparse": dict(              # cold documents, evidence, night: held low strings, bowed metal, single notes
        bpm=70, key="E", mode="minor", prog=[1, 6, 1, 7], swing=0.0, reverb=(0.8, 0.3), jitter_ms=14,
        pad=dict(kind="drone", inst="cellos", min=0.0), bass=dict(kind="synth", pattern="x...............", min=0.4),
        pulse=dict(kind="arp", inst="vibraphone", pattern="x.......x.......", min=0.5),
        drums=dict(kick=("gran_cassa", "hit", "x...............", 0.8), snare=None, hat=None, perc=("timpani", "drum1", "........x.......", 0.9)),
        lead=dict(inst="vibraphone_bowed", octave=5, motif=[0, 2, 1, 0], rhythm=[0, 4, 8, 12], min=0.35, vel=0.4, sparkle="glockenspiel"),
        sidechain=0.0, impact="cinematic"),
    "city-pop": dict(                  # 80s city pop / synth funk / anime opening: slap bass, FM keys, gated snare, sax lead
        bpm=116, key="E", mode="major", prog=[4, 5, 3, 6], swing=0.0, reverb=(0.45, 0.18), sevenths=True, jitter_ms=5,
        pad=dict(kind="comp", inst="epiano", pattern="x..x..x...x..x..", min=0.0), bass=dict(kind="sample", inst="electric_bass", pattern="x..x..x.x.x..x..", min=0.25),
        pulse=dict(pattern="x.x.x.x.x.x.x.x.", min=0.5, cutoff=(900, 6000), arp=True),
        drums=dict(kick=("drum_kit", "kick_drum_left", "x.....x...x.....", 0.5), snare=("drum_kit", "snare_2", "....x.......x...", 0.55),
                   hat=("hihat", "closed", "xxxxxxxxxxxxxxxx", 0.45), perc=("toms", "high", "..............oo", 0.85)),
        lead=dict(inst="alto_sax", octave=5, motif=[4, 5, 4, 2, 0, 2], rhythm=[0, 2, 3, 6, 8, 12], min=0.6, vel=0.55),
        sidechain=0.25, impact="clean", gated_snare=True),
    "rock-opening": dict(              # anime-opening rock: power chords, melodic bass, tight drums, 150–170 BPM
        bpm=160, key="E", mode="minor", prog=[6, 7, 1, 1], swing=0.0, reverb=(0.3, 0.12), jitter_ms=4,
        pad=dict(kind="power", inst="electric_guitar", min=0.0), bass=dict(kind="sample", inst="electric_bass", pattern="x.x.x.x.x.x.x.x.", min=0.2),
        pulse=None,
        drums=dict(kick=("drum_kit", "kick_drum_left", "x.....x.x.......", 0.4), snare=("drum_kit", "snare_1", "....x.......x...", 0.45),
                   hat=("drum_kit", "ride_left", "x.x.x.x.x.x.x.x.", 0.5), perc=("drum_kit", "crash_left", "x...............", 0.9)),
        lead=dict(inst="square", octave=5, motif=[0, 2, 4, 5, 4, 2, 4], rhythm=[0, 2, 4, 6, 8, 10, 12], min=0.6, vel=0.5),
        sidechain=0.0, impact="cinematic"),
}

# Drum families a style can swap in for its genre's kit (same patterns, other instruments). "genre" keeps the genre's own.
KITS = {
    "brushes": dict(kick=("drum_kit", "kick_drum_left"), snare=("snare2", "taps"), hat=("drum_kit", "ride_left"), perc=("shaker", "down")),
    "hand":    dict(kick=("cajon", "bass"), snare=("cajon", "slap"), hat=("shaker", "down"), perc=("conga", "conga")),
    "wood":    dict(kick=("log_drum", "lo"), snare=("woodblock", "a"), hat=("claves", None), perc=("log_drum", "hi")),
    "orch":    dict(kick=("gran_cassa", "hit"), snare=("snare", "on"), hat=("snare2", "taps"), perc=("timpani", "drum2")),
    "taiko":   dict(kick=("bass_drum", None), snare=("frame_drum", "small"), hat=("woodblock", "c"), perc=("frame_drum", "large")),
    "chip":    dict(kick=("chip", "kick"), snare=("chip", "snare"), hat=("chip", "hat"), perc=None),
    "machine": dict(kick=("chip", "kick808"), snare=("claps", "group"), hat=("chip", "hat"), perc=("shaker", "down")),
    "kit":     dict(kick=("drum_kit", "kick_drum_left"), snare=("drum_kit", "snare_1"), hat=("hihat", "closed"), perc=("toms", "low")),
}

# ---------- synthesis helpers ----------
rng = np.random.default_rng(1)
hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)
tt_ = lambda d: np.arange(max(1, int(d * SR))) / SR


def lp(x, f):
    return sosfilt(butter(2, min(f, SR / 2 - 100), "low", fs=SR, output="sos"), x)


def hp(x, f):
    return sosfilt(butter(2, f, "high", fs=SR, output="sos"), x)


def env(n, a=0.005, r=0.08):
    e = np.ones(n); ai, ri = max(1, int(a * SR)), max(1, int(r * SR))
    e[:ai] = np.linspace(0, 1, ai)[: n]; e[-min(ri, n):] *= np.linspace(1, 0, min(ri, n))
    return e


def saw(m, d, cents=0.0):
    t = tt_(d); f = hz(m) * 2 ** (cents / 1200)
    return 2 * ((t * f + rng.random()) % 1) - 1


def supersaw(m, d, voices=7, spread=22):
    return sum(saw(m, d, c) for c in np.linspace(-spread, spread, voices)) / voices


def pulse(m, d, duty=0.5):
    t = tt_(d); return np.where((t * hz(m)) % 1 < duty, 1.0, -1.0) * 0.6


def triangle4(m, d):                      # NES-like 4-bit stepped triangle
    t = tt_(d); x = 2 * np.abs(2 * ((t * hz(m)) % 1) - 1) - 1
    return np.round(x * 7.5) / 7.5


def theremin(m, d):                       # sine + a little 2nd/3rd, vibrato fading in ~150 ms after the onset
    t = tt_(d); vib = 0.3 * np.clip((t - 0.15) / 0.3, 0, 1) * np.sin(2 * np.pi * 5.5 * t)
    ph = 2 * np.pi * np.cumsum(hz(m) * 2 ** (vib / 12)) / SR
    return (np.sin(ph) + 0.2 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)) * env(len(t), 0.06, 0.12)


def sinebell(m, d):
    t = tt_(max(d, 1.2)); f = hz(m)
    return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t / 0.25)) * np.exp(-t / 0.9) * env(len(t), 0.002, 0.05)


def epiano(m, d):                         # FM electric piano with a bell transient
    t = tt_(max(d, 0.8)); f = hz(m); idx = 2.2 * np.exp(-t / 0.25)
    x = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t)) + 0.2 * np.sin(2 * np.pi * 14 * f * t) * np.exp(-t / 0.02)
    return x * np.exp(-t / 1.2) * env(len(t), 0.002, 0.08) * 0.6


def synth_bass(m, d):                    # sub + 2nd/3rd harmonics so it speaks on phones (TECHNIQUE §5)
    t = tt_(d); f = hz(m)
    x = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.18 * np.sin(6 * np.pi * f * t)
    return np.tanh(1.4 * x) * env(len(t), 0.004, 0.05)


def pluck_synth(m, d):
    t = tt_(d)
    x = supersaw(m, d, 3, 8) * np.exp(-t / 0.18)
    return lp(x, 3500) * env(len(t), 0.002, 0.04)


def warm_pad(m, d):
    x = supersaw(m, d, 5, 12); return lp(x, 1800) * env(len(x), 0.3, 0.4) * 0.6


SYNTHS = {"square": lambda m, d: pulse(m, d, 0.5) * env(int(d * SR), 0.002, 0.02),
          "pulse25": lambda m, d: pulse(m, d, 0.25) * env(int(d * SR), 0.002, 0.02),
          "pulse12": lambda m, d: pulse(m, d, 0.125) * env(int(d * SR), 0.002, 0.02),
          "triangle": lambda m, d: triangle4(m, d) * env(int(d * SR), 0.002, 0.02),
          "saw": lambda m, d: lp(supersaw(m, d, 3, 10), 3000) * env(int(d * SR), 0.01, 0.1),
          "supersaw": lambda m, d: lp(supersaw(m, d), 4000) * env(int(d * SR), 0.02, 0.12),
          "pluck": pluck_synth, "theremin": theremin, "sinebell": sinebell, "epiano": epiano,
          "synthbass": synth_bass, "pad": warm_pad}


def chip_drum(var, v):
    if var in ("kick", "kick808"):
        d = 0.12 if var == "kick" else 0.45; t = tt_(d); f = 45 + (110 if var == "kick" else 70) * np.exp(-t / 0.03)
        return np.tanh(1.5 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t / (d / 3)) * v
    d = 0.11 if var == "snare" else 0.035; n = np.sign(rng.standard_normal(int(d * SR)))        # LFSR-like 1-bit noise
    x = n * np.exp(-tt_(d) / (d / 3))
    return (hp(x, 6000) * 0.5 if var == "hat" else x * 0.7) * v


def riser(d):
    n = int(d * SR); t = np.arange(n) / SR; k = t / d
    nz = rng.standard_normal(n); out = np.zeros(n)
    for i in range(0, n, 1024):                          # band sweep up
        f = 300 * (40 ** k[i]); seg = nz[max(0, i - 2048):i + 1024]
        out[i:i + 1024] = sosfilt(butter(2, [f * 0.7, min(f * 1.4, SR / 2 - 200)], "band", fs=SR, output="sos"), seg)[-len(out[i:i + 1024]):]
    tone = np.sin(2 * np.pi * np.cumsum(hz(48) * (1 + 3 * k ** 2)) / SR) * 0.25
    return (out / (np.abs(out).max() + 1e-9) * 0.8 + tone) * k ** 2.2


def boom(d=2.5):                          # sub drop for impacts
    t = tt_(d); f = 30 + 55 * np.exp(-t / 0.08)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.7)


def put(buf, x, at, gain=1.0, pan=0.0):
    x = np.asarray(x, np.float64)
    if x.ndim == 1:
        x = np.stack([x * np.cos((pan + 1) * np.pi / 4), x * np.sin((pan + 1) * np.pi / 4)], 1) * 1.414
    s = int(round(at * SR))
    if s < 0: x, s = x[-s:], 0
    e = min(len(buf), s + len(x))
    if e > s: buf[s:e] += x[: e - s] * gain


def to_st(x):
    return np.stack([x, x], 1) if x.ndim == 1 else x


def db(v):
    return 10 * np.log10(v + 1e-20)


def bands(mix):
    spec = np.abs(np.fft.rfft(mix.mean(1))) ** 2; f = np.fft.rfftfreq(len(mix), 1 / SR)
    tot = spec[(f >= 20) & (f < 16000)].sum()
    return db(spec[(f >= 20) & (f < 120)].sum() / spec[(f >= 120) & (f < 16000)].sum()), db(spec[(f >= 2000) & (f < 6000)].sum() / tot)


def balance(mix, low_target=-3.0, presence_min=-12.0, lift=True):
    """Measured mastering EQ. Synth scores get bass-heavy and dull: bring 20-120 Hz to about -3 dB against the rest
    (lemo TECHNIQUE §5) and lift 2-6 kHz until it holds at least presence_min dB of the total."""
    for _ in range(4):                     # a filter-split shelf is approximate (phase), so measure and cut again
        over = bands(mix)[0] - low_target
        if over <= 0.5: break
        lows = np.stack([lp(mix[:, c], 120) for c in (0, 1)], 1)
        mix = mix - lows * (1 - 10 ** (-over / 20))
    for _ in range(3 if lift else 0):      # and a thin one (triangle or pizzicato bass) gets a measured low lift, max +4.5 dB;
        under = (low_target - 2) - bands(mix)[0]   # a band with no bass layer is thin by design: lifting it would only raise booms and reverb rumble
        if under <= 0.5: break
        lows = np.stack([lp(mix[:, c], 120) for c in (0, 1)], 1)
        mix = mix + lows * (10 ** (min(4.5, under) / 20) - 1)
    pres = bands(mix)[1]
    if pres < presence_min:
        highs = np.stack([hp(mix[:, c], 2000) for c in (0, 1)], 1)
        mix = mix + highs * (10 ** (min(9, presence_min - pres) / 20) - 1)
    return mix


# ---------- voices ----------
used = set()          # sampled instruments (credits)
voiced_as = set()     # every voice that sounded, synths and plucks included (the style's avoid list is checked on this)
fallbacks = set()     # pluck:* voices that fell back to harp (numba missing)


def voice(name, m, d, vel=0.6):
    """Any voice by name: a synth (SYNTHS), 'pluck:<preset>' (physically modelled), or a sampled instrument."""
    voiced_as.add(name)
    if name in SYNTHS: return SYNTHS[name](m, d) * (0.4 + 0.6 * vel)
    if name.startswith("pluck:"):
        if P is not None: return P.pluck(name[6:], fit(name, m), d, vel=vel)
        fallbacks.add(name); name = "harp"
    used.add(name)
    return S.note(name, fit(name, m), d, vel=vel)


def fit(name, m):                         # keep a note inside the instrument's sampled range (octave folding)
    if name.startswith("pluck:"): lo, hi = 36, 84
    elif name in SYNTHS: return m
    else:
        i = S.load(name); lo, hi = (i.lo or 0), (i.hi or 127)
    while m < lo: m += 12
    while m > hi: m -= 12
    return m


def drum(inst, var, v):
    if inst == "chip": return chip_drum(var, v)
    used.add(inst); return S.hit(inst, var, v)


# ---------- theory ----------
def scale(g):
    return MODES[g["mode"]]


def chord(g, deg, octave=4, seventh=False):
    sc = scale(g); root = 12 * (octave + 1) + NOTE[g["key"]]; n = len(sc)
    idx = [deg - 1, deg + 1, deg + 3] + ([deg + 5] if seventh else [])
    return [root + sc[i % n] + 12 * (i // n) for i in idx]


def voiced(ch, prev, lo=52, hi=76):
    """The inversion of ch nearest to the previous voicing (smooth voice leading), kept inside lo..hi."""
    opts = []
    for inv in range(len(ch)):
        v = sorted(ch[inv:] + [m + 12 for m in ch[:inv]])
        while v[0] < lo: v = [m + 12 for m in v]
        while v[-1] > hi: v = [m - 12 for m in v]
        opts.append(v)
    if not prev: return opts[0]
    return min(opts, key=lambda v: sum(abs(a - b) for a, b in zip(v, prev)))


def scale_note(g, step, octave):
    sc = scale(g); root = 12 * (octave + 1) + NOTE[g["key"]]; n = len(sc)
    return root + sc[step % n] + 12 * (step // n)


def nearest_chord_step(g, step, deg):
    n = len(scale(g)); tones = [(deg - 1 + k) % n for k in (0, 2, 4)]
    return min((step + o for o in range(-3, 4)), key=lambda s: (s % n not in tones, abs(s - step)))


def phrase(g, ld, bar_in_phrase, deg):
    """4-bar phrase from one motif: statement / sequence on the chord / repeat / answer with a cadence on the tonic."""
    motif, rhythm = list(ld["motif"]), list(ld["rhythm"])
    if bar_in_phrase == 1: motif = [s + deg - 1 for s in motif]
    if bar_in_phrase == 3:
        k = max(2, len(motif) // 2); motif = motif[:k] + [0]; rhythm = rhythm[:k] + [max(8, rhythm[k - 1] + 2)]
    out = []
    for i, (st, r) in enumerate(zip(motif, rhythm)):
        if r % 4 == 0: st = nearest_chord_step(g, st, deg)               # strong beats sit on chord tones
        ln = (rhythm[i + 1] - r) if i + 1 < len(rhythm) else 16 - r
        out.append((st, r, ln))
    return out


def resolve(plan):
    """genre < style ensemble < topic mood < explicit plan keys → one settings dict g, plus the ensemble."""
    ens = dict(plan.get("ensemble") or {})
    if plan.get("style"):
        ens = {**json.loads(Path(plan["style"]).read_text("utf8"))["stylist"].get("score", {}), **ens}
    genre = plan.get("genre") or ens.get("genre") or "cinematic-pulse"
    if genre == "none":
        raise SystemExit("this style has no score (music only inside the world): build the diegetic sound instead, guide 'music'")
    g = json.loads(json.dumps(GENRES[genre]))
    g["duck_db"] = DUCK.get(genre, -10.0)
    if ens.get("space"): g.update(SPACES[ens["space"]])
    for k in ("bpm", "key", "mode", "prog", "swing", "sevenths", "jitter_ms", "laid_back_ms", "gated_snare", "sidechain", "reverb", "impact",
              "lowpass", "highpass", "tape", "duck_db"):
        if k in ens: g[k] = ens[k]
    if ens and "bpm" not in ens:   # ponytail: 23 styles share minimal-pulse; a stable ±4 BPM per band keeps them apart. Set "bpm" to pin it
        g["bpm"] += zlib.crc32(json.dumps(ens, sort_keys=True).encode()) % 9 - 4
    for layer in ("pad", "bass", "lead", "pulse"):
        if layer in ens:
            v = ens[layer]
            if v is None: g[layer] = None
            elif isinstance(v, dict): g[layer] = {**(g.get(layer) or {"min": 0.3}), **v}
            else:
                base = dict(g.get(layer) or {"min": {"pad": 0, "bass": .25, "pulse": .45, "lead": .5}[layer], "pattern": "x.......x......."})
                base["inst"] = v
                if layer == "pad" and base.get("kind") not in ("comp", "arp", "drone", "power"):
                    base["kind"] = "synth" if v in SYNTHS else ("comp" if (not v.startswith("pluck:") and S.load(v).kind == "dec") or v.startswith("pluck:") else "sample")
                if layer == "bass": base["kind"] = "synth" if v in SYNTHS else "sample"
                if layer == "pulse": base["kind"] = "arp"
                g[layer] = base
    for k in ("counter", "sparkle", "avoid"):
        if k in ens: g[k] = ens[k]
    if ens.get("sparkle") and g.get("lead"): g["lead"]["sparkle"] = ens["sparkle"]
    kit = ens.get("drums", "genre")
    if kit == "none": g["drums"] = {}
    elif kit in KITS:
        g["drums"] = {r: (KITS[kit][r] + (spec[2], spec[3]) if spec and KITS[kit].get(r) else None) for r, spec in g["drums"].items()}
    mood = MOODS.get(plan.get("mood") or "", {})
    for k, v in mood.items():
        if k in ens: continue                                        # the style's own mode / progression survives the mood
        g[k] = g["bpm"] + v if k == "bpm" else v
    for k in ("bpm", "key", "mode", "prog"):
        if k in plan: g[k] = plan[k]
    return genre, g


# ---------- the arranger ----------
def render(plan, out_dir):
    global rng
    used.clear(); voiced_as.clear(); fallbacks.clear()
    genre, g = resolve(plan)
    rng = np.random.default_rng(plan.get("seed", 1)); S.seed(plan.get("seed", 1))
    dur, beat = float(plan["dur"]), 60.0 / g["bpm"]
    step = beat / 4; bar = beat * 4
    snap = lambda t: round(t / beat) * beat
    secs = sorted(({**s, "t": snap(s["t"])} for s in plan["sections"]), key=lambda s: s["t"])
    energy_at = lambda t: max([s for s in secs if s["t"] <= t + 1e-6] or secs[:1], key=lambda s: s["t"])["energy"]
    starts = [s["t"] for s in secs]
    peak_e = max(s["energy"] for s in secs)
    n = int((dur + 4) * SR)
    stems = {k: np.zeros((n, 2)) for k in ("drums", "bass", "harmony", "pulse", "lead", "fx")}
    swing, jit = g.get("swing", 0.0), g.get("jitter_ms", 6) / 1000
    swung = lambda i: i * step + ((swing - 0.5) * 2 * step if swing and i % 2 else 0)
    human = lambda: rng.normal(0, jit) if jit else 0.0
    accent = lambda i: (1.0 if i % 4 == 0 else 0.88 if i % 2 == 0 else 0.76) * rng.uniform(0.93, 1.05)
    stats = {"motif": 0, "first_hook": None, "melody": [], "seam_fills": 0}
    # seams: the trailer kit (noise riser + sub boom + crash + tom fill on every cut) is what makes a score sound stock.
    # riser: noise | musical (an in-key run on the band's own instrument) | none; fills: every | rise (only into a lift) | none;
    # impact: sub boom + crash on section starts; hit: trailer (boom + reverse crash) | crash | none
    sm = {"riser": "noise", "fills": "every", "impact": True, "hit": "trailer", **plan.get("seams", {})}
    lifts = {s["t"] for a, s in zip(secs, secs[1:]) if s["energy"] > a["energy"] + 0.15}

    nbars = int(np.ceil(dur / bar)) + 1
    prog = g["prog"]; prev_v = None
    for b in range(nbars):
        t0 = b * bar
        if t0 >= dur: break
        deg = prog[b % len(prog)]; nxt = prog[(b + 1) % len(prog)]
        ch = chord(g, deg, 3, g.get("sevenths", False)); v = voiced(ch, prev_v); prev_v = v
        e = energy_at(t0)
        seam = next((s for s in starts[1:] if t0 < s <= t0 + bar + 1e-6), None)     # a section starts inside / at the end of this bar
        sec_i = max(i for i, s in enumerate(starts) if s <= t0 + 1e-6) if any(s <= t0 + 1e-6 for s in starts) else 0
        bar_in_phrase = int(round((t0 - starts[sec_i]) / bar)) % 4

        # harmony
        p = g.get("pad")
        if p and e >= p["min"]:
            k, inst = p.get("kind"), p.get("inst")
            if k == "strings":
                for m in v:
                    nm = "cellos" if m < 55 else "violins"; used.add(nm)
                    put(stems["harmony"], S.note(nm, m + 12, bar * 1.02, vel=0.35 + 0.4 * e, attack=0.25), t0, 0.5, rng.uniform(-.4, .4))
            elif k == "supersaw" or (k == "synth" and inst in ("supersaw", "pad")):
                voiced_as.add(inst or "supersaw")
                x = sum(SYNTHS["pad"](m + 12, bar) for m in v) / len(v) if inst == "pad" else sum(supersaw(m + 12, bar) for m in v) / len(v)
                put(stems["harmony"], lp(x, 900 + 5000 * e) * env(len(x), 0.02, 0.12), t0, 0.35)
            elif k == "sample" or k == "synth":
                for j, m in enumerate(v):
                    put(stems["harmony"], voice(inst, m + 12, bar * 1.02, 0.3 + 0.35 * e), t0 + j * 0.018, 0.4, (j - 1) * 0.3)   # piano-like roll, 18 ms a note
            elif k == "drone":
                for m in (v[0] - 12, v[0] - 5):
                    x = voice(inst, m, bar * 1.05, 0.3 + 0.3 * e)
                    put(stems["harmony"], x * env(len(x), 0.4, 0.4), t0, 0.5, rng.uniform(-.3, .3))
            elif k == "power":                                       # root-fifth-octave on 8ths, palm-muted below the peak
                for i in range(0, 16, 2):
                    for m in (v[0] - 12, v[0] - 5, v[0]):
                        put(stems["harmony"], np.tanh(2.5 * voice(inst, m, step * (1.8 if e >= 0.9 else 1.0), 0.7)), t0 + swung(i) + human(), 0.25)
            elif k == "arp":                                         # ostinato through the voicing, one note per 8th
                pat = p.get("pattern", "x.x.x.x.x.x.x.x.")
                for i, c in enumerate(pat):
                    if c == ".": continue
                    m = v[(i // 2) % len(v)] + 12
                    put(stems["harmony"], voice(inst, m, step * 2.2, accent(i) * (0.35 + 0.3 * e)), t0 + swung(i) + human(), 0.45, (-.3 if i % 4 else .3))
            else:                                                    # comp: chord stabs on the comp rhythm
                pat = p.get("pattern", "x.....x...x.....")
                for i, c in enumerate(pat):
                    if c == ".": continue
                    if (inst or "").startswith("pluck:") and P is not None:
                        x = P.strum(inst[6:], [m + 12 for m in v], beat * 1.6, vel=accent(i) * (0.4 + 0.25 * e))
                        put(stems["harmony"], x, t0 + swung(i) + human(), 0.5)
                        continue
                    for j, m in enumerate(v):
                        put(stems["harmony"], voice(inst or "piano", m + 12, beat * 1.6, accent(i) * (0.35 + 0.2 * e)),
                            t0 + swung(i) + j * 0.018 + human(), 0.5, (j - 1.5) * 0.15)
        # bass
        bs = g.get("bass")
        if bs and e >= bs["min"]:
            root = v[0] - 12; lb = g.get("laid_back_ms", 0) / 1000
            inst = bs.get("inst") or ("synthbass" if bs.get("kind") == "synth" else "jazz_bass")
            if bs.get("walk"):                                       # walking bass: root, chord tone, fifth, approach to the next root
                nroot = chord(g, nxt, 2)[0]
                line = [root, v[1] - 12, v[2] - 12, nroot + (1 if nroot < root else -1)]
                for q, m in enumerate(line):
                    put(stems["bass"], voice(inst, m, beat * 0.95, accent(q * 4) * 0.7), t0 + q * beat + lb + human(), 0.85)
            else:
                pat = bs.get("pattern", "x.......x.......")
                for i, c in enumerate(pat):
                    if c == ".": continue
                    m = root + (12 if bs.get("octaves") and i % 2 else 0)
                    ln = step * (1.8 if pat.count("x") > 8 else 3.5)
                    gain = 0.2 if inst == "synthbass" else 0.3 if inst == "triangle" else 0.85
                    put(stems["bass"], voice(inst, m, ln, accent(i) * 0.7), t0 + swung(i) + lb + human(), gain)
        # pulse / arp
        pu = g.get("pulse")
        if pu and e >= pu["min"]:
            if pu.get("kind") in ("arp", "comp"):
                for i, c in enumerate(pu["pattern"]):
                    if c == ".": continue
                    m = v[i % len(v)] + 24
                    put(stems["pulse"], voice(pu["inst"], m, step * 2.5, accent(i) * (0.3 + 0.3 * e)), t0 + swung(i) + human(), 0.35, 0.3 if i % 2 else -0.3)
            else:
                lo, hi = pu["cutoff"]; cut = lo + (hi - lo) * min(1, (e - pu["min"]) / (1 - pu["min"] + 1e-9))
                for i, c in enumerate(pu["pattern"]):
                    if c == ".": continue
                    m = v[i % len(v)] + 12 if pu.get("arp") else v[0] + (12 if i % 4 == 2 else 0) + 12
                    x = saw(m, step * 0.9) if not pu.get("soft") else np.sin(2 * np.pi * hz(m + 12) * tt_(step * 2)) * np.exp(-tt_(step * 2) / 0.3)
                    put(stems["pulse"], lp(x, cut) * env(len(x), 0.003, 0.03), t0 + swung(i), 0.22 * accent(i), 0.3 if i % 2 else -0.3)
        # drums, with a fill into the next section
        fill = seam is not None and any(sp for sp in g["drums"].values()) and (sm["fills"] == "every" or (sm["fills"] == "rise" and seam in lifts))
        in_fill = lambda at: fill and seam - beat - 1e-6 <= at < seam
        for name, spec in g["drums"].items():
            if not spec: continue
            inst, var, pat, mn = spec
            if e < mn: continue
            for i, c in enumerate(pat):
                if c == ".": continue
                if in_fill(t0 + swung(i)) and name in ("snare", "hat", "perc"): continue
                vv = (0.85 if c == "x" else 0.5) * (0.8 + 0.2 * e) * (accent(i) if name == "hat" else rng.uniform(0.94, 1.03))
                x = drum(inst, var, vv)
                gain = {"kick": 0.9, "snare": 0.85, "hat": 0.55, "perc": 0.5}[name]
                if name == "snare" and g.get("gated_snare"):
                    x = to_st(x); x = S.room(x, size=0.7, mix=0.5)[: int(0.28 * SR)] * env(int(0.28 * SR), 0.001, 0.03)[:, None]
                put(stems["drums"], x, t0 + swung(i) + human() * 0.5, gain, {"hat": 0.25, "perc": -0.3}.get(name, 0))
        if fill:
            stats["seam_fills"] += 1
            kit = next(sp[0] for sp in g["drums"].values() if sp)
            for j in range(4):
                if kit == "chip": x = chip_drum("kick", 0.6) if j % 2 else chip_drum("snare", 0.6)
                elif kit in ("drum_kit", "hihat", "claps", "snare2", "snare"): x = drum("toms", "high" if j < 2 else "low", 0.6 + 0.1 * j)
                else: x = drum(kit, g["drums"]["kick"][1] if g["drums"].get("kick") else None, 0.5 + 0.1 * j)
                put(stems["drums"], x, seam - beat + j * step, 0.6, 0.4 - 0.25 * j)
        elif seam is not None and sm["fills"] != "none" and (sm["fills"] == "every" or seam in lifts) and (g.get("lead") or {}).get("sparkle"):   # no kit: a sparkle run
            for j in range(4):
                put(stems["lead"], voice(g["lead"]["sparkle"], scale_note(g, 4 + j, 6), 0.6, 0.35), seam - beat + j * step, 0.4, -0.3 + 0.2 * j)

        # melody: lead and counter trade bars, merge at the peak
        ld = g.get("lead")
        if ld and 0.2 <= e < ld["min"] and bar_in_phrase in (0, 2):      # below the lead's energy: plant the hook softly
            hint = g.get("counter") or ld.get("sparkle") or ld["inst"]
            for st, r, ln in phrase(g, ld, 0, deg):
                m = scale_note(g, st, ld["octave"] + (1 if hint != ld["inst"] else 0))
                put(stems["lead"], voice(hint, m, max(step * 1.5, ln * step * 0.9), ld["vel"] * 0.55 * accent(r)), t0 + swung(r) + human(),
                    0.22 if hint in SYNTHS else 0.45, -0.2)
                stats["melody"].append(m)
            stats["motif"] += 1
            if stats["first_hook"] is None: stats["first_hook"] = round(t0, 3)
        if ld and e >= ld["min"]:
            ctr = g.get("counter"); peak = e >= peak_e - 1e-6 and peak_e >= 0.9
            players = [(ld["inst"], ld["octave"], ld["vel"])]
            if ctr:
                cv = (ctr, ld["octave"] + 1, ld["vel"] * 0.85)
                players = [players[0], cv] if peak else ([players[0]] if bar_in_phrase % 2 == 0 else [cv])
            for pi, (inst, octv, vel) in enumerate(players):
                climb = 12 if (peak and bar_in_phrase == 2 and pi == 0) else 0
                for st, r, ln in phrase(g, ld, bar_in_phrase, deg):
                    m = scale_note(g, st, octv) + climb
                    d = max(step * 1.5, ln * step * 0.95)
                    x = voice(inst, m, d, vel * accent(r) * (0.7 + 0.3 * e))      # the line plays louder as energy rises
                    at = t0 + swung(r) + human()
                    put(stems["lead"], x, at, 0.32 if inst in SYNTHS else 0.7, 0.15 - 0.3 * pi)
                    if inst == ld["inst"]: stats["melody"].append(m)        # range of the lead line itself
                    if ld.get("canon") and pi == 0:                     # imitative entry a half bar later, an octave down
                        put(stems["lead"], voice(inst, m - 12, d, vel * 0.7), at + 2 * beat, 0.45, -0.3)
            if bar_in_phrase in (0, 2):
                stats["motif"] += 1
                if stats["first_hook"] is None: stats["first_hook"] = round(t0, 3)
            if ld.get("sparkle") and b % 2:
                put(stems["lead"], voice(ld["sparkle"], scale_note(g, 4, 6), 2.0, 0.35), t0 + 2 * beat, 0.4, -0.4)

    # transitions: risers into rising sections, impacts on section starts, big hits, crackle
    for prev, s in zip(secs, secs[1:]):
        if s["energy"] > prev["energy"] + 0.15 and sm["riser"] == "musical":   # the band's own instrument runs up the scale into the cut
            ri = (g.get("lead") or {}).get("sparkle") or (g.get("lead") or {}).get("inst") or "harp"
            for j in range(8):
                put(stems["fx"], voice(ri, scale_note(g, j, 5), step * 1.6, 0.25 + 0.06 * j), s["t"] - 2 * beat + j * step, 0.45, -0.4 + 0.1 * j)
        elif s["energy"] > prev["energy"] + 0.15 and sm["riser"] == "noise":
            kit = bool(g["drums"])                                               # a band with no kit gets a short, quiet swell, not a trailer riser
            d = min(2 * bar if kit else bar, max(beat * 2, s["t"] - prev["t"]))
            put(stems["fx"], riser(d), s["t"] - d, 0.25 if kit else 0.06)
        if s["t"] > 0 and g["drums"] and sm["impact"]:                        # no kit, no sub booms on every seam (solo / chamber bands)
            put(stems["fx"], to_st(boom(1.6)) * 0.5, s["t"], 0.3)
            if g.get("impact") != "soft" and g["drums"]:
                chip = (g["drums"].get("kick") or ("",))[0] == "chip"
                put(stems["fx"], hp(np.sign(rng.standard_normal(int(0.6 * SR))) * np.exp(-tt_(0.6) / 0.18), 3000) * 0.4 if chip
                    else drum("drum_kit", "crash_left", 0.7), s["t"], 0.45, 0.2)
    for h in (plan.get("hits", []) if sm["hit"] != "none" else []):
        if sm["hit"] == "crash":
            put(stems["fx"], drum("crash", None, 0.75), h, 0.4); continue
        put(stems["fx"], to_st(boom(2.8)), h, 0.55)              # hits are picture events: exact time, not snapped
        if g.get("impact") == "cinematic":
            put(stems["fx"], drum("bass_drum", None, 1.0), h, 0.9); put(stems["fx"], drum("timpani", "drum1", 0.9), h, 0.6)
        if g["drums"] or g.get("impact") != "soft":
            crash = drum("crash", None, 0.8)
            put(stems["fx"], crash[::-1][-int(1.2 * SR):], h - 1.2, 0.35)       # reverse cymbal sucks into the hit
            put(stems["fx"], crash, h, 0.4)
        else:
            put(stems["fx"], voice("tubular_bells", scale_note(g, 0, 5), 3.0, 0.6), h, 0.5)
    for w in plan.get("swoops", []):                              # designed transition from the band's own voice, not a stock whoosh:
        d = 0.32; t = tt_(d); k = t / d                              # the counter/lead voice glides a fifth down past the camera
        f0 = hz(scale_note(g, 4, 6)); f = f0 * 2 ** (-7 / 12 * k ** 1.5)
        name = g.get("counter") or "square"; ph = np.cumsum(f) / SR
        x = (np.where(ph % 1 < 0.5, 1.0, -1.0) if name in ("square", "pulse25", "pulse12", "triangle") else np.sin(2 * np.pi * ph)) * np.sin(np.pi * k) ** 1.5
        x = lp(x, 5000) * 0.5
        put(stems["fx"], np.stack([x * (1 - k), x * k], 1) * 1.4, w - d * 0.5, 0.5)        # pans left to right across the cut
    lg = plan.get("logo")                                         # sonic logo: a short fixed figure at an exact picture time
    if lg:
        for st, r in zip(lg["steps"], lg["rhythm"]):
            last = r == lg["rhythm"][-1]
            put(stems["lead"], voice(lg.get("inst", "square"), scale_note(g, st, lg.get("octave", 5)), step * (6 if last else 1.6), lg.get("vel", 0.7)),
                lg["t"] + r * step, lg.get("gain", 0.35), 0.0)
    if g.get("crackle"):
        cr = np.zeros(n); idx = rng.integers(0, n, int(dur * 25)); cr[idx] = rng.uniform(-0.6, 0.6, len(idx))
        put(stems["fx"], to_st(hp(cr, 1500) + lp(rng.standard_normal(n), 3000) * 0.012), 0, 0.5)
    if g.get("echo"):                                                           # SNES-style echo on the melody
        dt, fb = g["echo"]; k = int(dt * SR); x = stems["lead"].copy()
        for r in range(1, 4):
            stems["lead"][k * r:] += lp_st(x[: n - k * r], 3500) * fb ** r

    # bus processing (plan "bus": "pedalboard", optional, GPLv3 package): glue the kit, parallel-saturate the bass so it speaks
    # on phones, a slight chorus to widen the keys; a master glue compressor after the balance
    pbm = None
    if plan.get("bus") == "pedalboard":
        try:
            import pedalboard as pbm
            f32 = lambda x: np.ascontiguousarray(x.T, np.float32)
            dr = f32(stems["drums"])
            stems["drums"] = (pbm.Pedalboard([pbm.Compressor(threshold_db=-20, ratio=4, attack_ms=8, release_ms=120)])(dr, SR)
                              + 0.22 * pbm.Pedalboard([pbm.Distortion(drive_db=14), pbm.LowpassFilter(6000)])(dr, SR)).T
            bs = f32(stems["bass"])
            stems["bass"] = (bs + 0.3 * pbm.Pedalboard([pbm.Distortion(drive_db=18), pbm.LowpassFilter(2500)])(bs, SR)).T
            stems["harmony"] = pbm.Pedalboard([pbm.Chorus(rate_hz=0.6, depth=0.15, mix=0.25)])(f32(stems["harmony"]), SR).T
        except ImportError:
            stats["bus_missing"] = True
    # sidechain pump from the kick grid, filter and space
    kspec = g["drums"].get("kick") if g["drums"] else None
    kicks = [b * bar + swung(i) for b in range(nbars) for i, c in enumerate(kspec[2]) if kspec and c != "." and energy_at(b * bar) >= kspec[3]] if kspec else []
    if g.get("sidechain") and kicks:
        tt = np.arange(n) / SR; pump = np.ones(n)
        for k in kicks:
            s = int(k * SR); m = min(n, s + int(0.3 * SR)); pump[s:m] = np.minimum(pump[s:m], 1 - g["sidechain"] * np.exp(-(tt[s:m] - k) / 0.09))
        for st in ("harmony", "pulse", "bass"): stems[st] *= pump[:, None]
    mix = sum(stems.values())
    size, wet = g["reverb"]
    mix = S.room(mix, size=size, mix=wet)
    if g.get("lowpass"): mix = lp_st(mix, g["lowpass"])
    hpf = max(28, g.get("highpass") or 0)
    mix = np.stack([hp(mix[:, 0], hpf), hp(mix[:, 1], hpf)], 1)
    if g.get("tape"):              # tape warmth: soft tanh saturation, peak-normalised so drive (0..1) only changes colour
        dr, pk = 1 + 4 * g["tape"], np.abs(mix).max() + 1e-9
        mix = np.tanh(dr * mix / pk) / np.tanh(dr) * pk
    # energy is loudness too: a 0.3 intro sits ~6 dB under a 1.0 drop (ramped, so section changes don't click)
    tt = np.arange(len(mix)) / SR
    e = np.array([energy_at(t) for t in tt[::480]]); e = np.repeat(e, 480)[: len(mix)]
    k = int(0.2 * SR); e = np.convolve(e, np.ones(k) / k, mode="same")
    mix *= (10 ** (-9 * (1 - e) / 20))[:, None]
    end = int(dur * SR); mix = mix[:end]   # trim first: the balance is measured on exactly what ships
    mix = balance(mix, lift=bool(g.get("bass")))
    if pbm is not None:
        mix = pbm.Pedalboard([pbm.Compressor(threshold_db=-16, ratio=2, attack_ms=20, release_ms=200)])(np.ascontiguousarray(mix.T, np.float32), SR).T.astype(np.float64)                     # after the energy curve, so the balance is measured on what is heard
    for a, b2 in plan.get("silences", []):
        sa, sb, f = int(a * SR), int(b2 * SR), int(0.03 * SR)
        mix[max(0, sa - f):sa] *= np.linspace(1, 0, sa - max(0, sa - f))[:, None]; mix[sa:sb] = 0
    if plan.get("end", "ring") == "button":
        f = int(0.06 * SR); mix[end - f:end] *= np.linspace(1, 0, f)[:, None]
    else:
        f = int(min(1.5, dur * 0.1) * SR); mix[end - f:end] *= np.linspace(1, 0, f)[:, None] ** 1.5
    mix = mix[:end]
    mix *= 10 ** (-18 / 20) / (np.sqrt(np.mean(mix ** 2)) + 1e-9)          # -18 dB RMS; mix_pro stages it against the voice
    mix = np.stack([limit(mix[:, 0], 0.89), limit(mix[:, 1], 0.89)], 1)

    out = Path(out_dir); (out / "stems").mkdir(parents=True, exist_ok=True)
    sf.write(out / "music.wav", mix.astype(np.float32), SR, subtype="PCM_24")
    for k, v in stems.items():
        if np.abs(v).max() > 0: sf.write(out / "stems" / f"{k}.wav", v[:end].astype(np.float32) * 0.5, SR, subtype="PCM_24")
    grid = [round(i * beat, 4) for i in range(int(dur / beat) + 1)]
    rep = {"genre": genre, "mood": plan.get("mood"), "bpm": g["bpm"], "duck_db": g["duck_db"], "key": f"{g['key']} {g['mode']}", "beat_s": round(beat, 4), "bar_s": round(bar, 4),
           "instruments": sorted(used | {v for v in voiced_as if v in SYNTHS or v.startswith("pluck:")}), "sections": [{"t": round(s["t"], 4), "energy": s["energy"]} for s in secs], "beats": grid,
           "credits": S.credits(sorted(i for i in used if i))}
    rep["critique"] = critique(mix, secs, dur, plan, g, stats)
    (out / "music_report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), "utf8")
    return rep


def lp_st(x, f):
    return np.stack([lp(x[:, 0], f), lp(x[:, 1], f)], 1)


def critique(mix, secs, dur, plan, g, st):
    """Adversarial critic (after YaO): only problems, each measured, located and with a fix. Empty = ship it."""
    out = []
    add = lambda sev, rule, where, fix: out.append({"severity": sev, "rule": rule, "where": where, "fix": fix})
    ends = [s["t"] for s in secs[1:]] + [dur]
    rms = []
    for s, e in zip(secs, ends):
        seg = mix[int(s["t"] * SR):int(e * SR)]
        if len(seg) > SR * 0.3:
            rms.append((s, db(np.mean(seg ** 2))))
    if len(rms) >= 2:
        lo, hi = min(r for _, r in rms), max(r for _, r in rms)
        if hi - lo < 4: add("major", "structure.flat_arc", "whole cue", f"loudest and quietest sections differ by {hi - lo:.1f} dB (< 4): lower the intro energy or raise the payoff")
        top_e = max(s["energy"] for s, _ in rms); loud = max(rms, key=lambda x: x[1])[0]
        if loud["energy"] < top_e - 0.15: add("major", "structure.climax_misplaced", f"{loud['t']:.2f} s", "the loudest section is not the payoff: give the payoff the highest energy and a hit")
        for (a, ra), (b, rb) in zip(rms, rms[1:]):
            if abs(a["energy"] - b["energy"]) >= 0.2 and abs(ra - rb) < 1.5:
                add("minor", "structure.section_monotony", f"{b['t']:.2f} s", "this section sounds like the last one: change the layer count or the register")
    need = 3 if dur >= 20 else 2                                     # a short cue has room for fewer statements
    if st["motif"] < need: add("major", "melody.motif_recurrence", "whole cue", f"the hook is stated {st['motif']}× (< {need}): lower lead.min or give the hook more bars")
    if st["first_hook"] is None or st["first_hook"] > 0.4 * dur:
        add("minor", "melody.hook_late", f"{st['first_hook']}", "the hook first appears after 40 % of the film: let it in earlier, quietly")
    if st["melody"]:
        span = max(st["melody"]) - min(st["melody"])
        if span < 5: add("major", "melody.contour_monotony", "lead", f"melody spans {span} semitones: widen the motif (a 5th–octave leap)")
        if span > 26: add("minor", "melody.range_wide", "lead", f"melody spans {span} semitones: fold the climax octave or narrow the motif")
    bad = sorted(set(g.get("avoid") or []) & (used | voiced_as))
    if bad: add("critical", "style.forbidden_instrument", ", ".join(bad), "the style's sound palette forbids these: swap them in the ensemble")
    if st.get("bus_missing"): add("minor", "acoustics.bus_missing", "bus", "plan asks for the pedalboard bus but the package is missing: pip install pedalboard")
    if fallbacks: add("major", "style.voice_fallback", ", ".join(sorted(fallbacks)), "played by harp samples because numba is missing: install it (pip install numba) and render again")
    low, pres = bands(mix)
    if low > -1.5: add("minor", "acoustics.boomy", "master", f"20–120 Hz is {low:.1f} dB vs the rest (target about -3): thin the bass layer")
    if pres < -14: add("minor", "acoustics.dull", "master", f"2–6 kHz holds {pres:.1f} dB (< -14): brighter lead or sparkle")
    for a, b in plan.get("silences", []):
        seg = mix[int(a * SR):int(b * SR)]
        if len(seg) and db(np.mean(seg ** 2)) > -60: add("major", "structure.silence_leak", f"{a}-{b} s", "the planned silence is not silent")
    return out


if __name__ == "__main__":
    plan = json.loads(Path(sys.argv[1]).read_text("utf8"))
    r = render(plan, sys.argv[2])
    print(f"{r['genre']} ({r['mood'] or 'no mood'}) {r['bpm']} bpm {r['key']}: sections at {[s['t'] for s in r['sections']]} -> {Path(sys.argv[2]) / 'music.wav'}")
    print("instruments:", ", ".join(r["instruments"]))
    for c in r["critique"]: print(f"  [{c['severity']}] {c['rule']} @ {c['where']}: {c['fix']}")
    if not r["critique"]: print("  critique: clean")

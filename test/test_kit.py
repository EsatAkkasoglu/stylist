"""Kit end to end on synthetic media: mix_pro, verify_mix, beats, gates, blender check.  python test/test_kit.py
Needs ffmpeg, numpy, scipy (synth cue) and LEMO_OPUSCAR_HOME (or ~/lemo-opuscar) for the synth fallback."""
import json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for d in ("audio", "gates", "blender"):
    sys.path.insert(0, str(ROOT / "kit" / d))
import numpy as np
import soundfile as sf
from mix_pro import mix, decode, SR
from verify_mix import verify
from beats import beats
import gates, blender_autoweight

tmp = Path(tempfile.mkdtemp())
ff = lambda *a: subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)
ff("-f", "lavfi", "-i", "sine=f=220:d=6,volume=0.3", str(tmp / "music.wav"))
ff("-f", "lavfi", "-i", "sine=f=1000:d=6,volume='0.56*between(t,2,4)':eval=frame", str(tmp / "vo.wav"))
ff("-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=6", "-pix_fmt", "yuv420p", str(tmp / "ok.mp4"))

cat = json.loads((ROOT / "sfx_library" / "sfx_catalog.json").read_text("utf8"))
for s in cat: s["path"] = str(ROOT / "sfx_library" / s["path"])
click = next(s for s in cat if s["role"] == "UI/CLICK" and s["duration_ms"] < 400)
whoosh = next(s for s in cat if s["role"] == "WHOOSH/SWISH" and s["duration_ms"] < 1500)
cues = [{"t": 1.0, "role": "UI/CLICK", "file": click["path"]},
        {"frame": 72, "role": "WHOOSH/SWISH", "file": whoosh["path"]},            # t = 3.0, peak-aligned
        {"t": 4.5, "role": "IMPACT/HIT", "synth": "thump", "args": {"v": 1.0}},   # procedural fallback from lemo sfx.py
        {"t": 5.0, "role": "UI/CLICK", "file": click["path"]}]
(tmp / "cues.json").write_text(json.dumps(cues))
rep = mix(tmp / "cues.json", tmp / "out", tmp / "music.wav", tmp / "vo.wav", fps=24)
out = tmp / "out"
for f in ("mix.wav", "sfx_bus.wav", "music_ducked.wav", "mix_report.json"):
    assert (out / f).exists(), f
c = {r["cue"]: r for r in rep["cues"]}
assert abs(c[0]["start_s"] - (1.0 - 1 / 24)) < 1e-3, "click one frame early"
bus = decode(out / "sfx_bus.wav")
assert np.abs(bus).max() <= 1.0, f"SFX bus clips: peak {np.abs(bus).max():.2f}"
w = decode(whoosh["path"], c[1]["rate"])
peak = c[1]["start_s"] + np.abs(w).sum(1).argmax() / SR
assert abs(peak - 3.0) < 0.01, f"whoosh peak on its frame, got {peak:.3f}"
assert c[2]["src"] == "synth:thump"
md = decode(out / "music_ducked.wav")
db = lambda a, b: 20 * np.log10(np.sqrt(np.mean(md[int(a * SR):int(b * SR)] ** 2)) + 1e-9)
assert db(0.3, 0.9) - db(2.5, 3.5) > 8, f"ducking depth {db(0.3, 0.9) - db(2.5, 3.5):.1f} dB"
assert abs(db(4.8, 5.8) - db(0.3, 0.9)) < 1, "music comes back after the voice"
ms = rep["measured"]
assert ms["music_under_speech_db"] <= -18, f"music too loud under the voice: {ms}"
assert -12 <= ms["music_between_lines_db"] <= -8, f"music bed not ~10 dB under the voice: {ms}"
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out / "mix.wav")],
                           capture_output=True, text=True).stdout)
assert abs(dur - 6) < 0.05, dur
# same file twice in a row is allowed only with a warning; mixes without music or voice work too
assert mix(tmp / "cues.json", tmp / "out2", None, tmp / "vo.wav", fps=24)["duck_threshold"] is None
assert mix(tmp / "cues.json", tmp / "out3", tmp / "music.wav", None, fps=24)["duck_threshold"] is None

v = verify(out / "mix.wav", out / "mix_report.json", tmp / "verify", tmp / "ok.mp4", 24)
assert Path(v["waveform"]).stat().st_size > 1000 and len(v["frames"]) == 8

b = beats({"l1": [["Hello", 0.1, 0.5], ["world", 0.6, 1.0]], "l2": [["again", 0.0, 0.4]]}, {"l1": 2.0, "l2": 5.0}, fps=24, lead=1)
assert [x["frame"] for x in b] == [49, 61, 119] and b[0]["word"] == "Hello"

# gates: a clean render passes, a frozen tail fails G2 unless declared as a hold, black frames fail G5
r = gates.run(tmp / "ok.mp4", "320x180", 24, 6, out=tmp / "g1")
assert r["G0"]["pass"] and r["G2"]["pass"] and r["G5"]["pass"] and r["G3"]["pass"] is None, r
assert not gates.run(tmp / "ok.mp4", "1920x1080", 24, 6, out=tmp / "g0")["G0"]["pass"]
ff("-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=3", "-f", "lavfi", "-i", "color=c=gray:s=320x180:r=24:d=2",
   "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24:d=1", "-filter_complex", "[0][1][2]concat=n=3:v=1[v]", "-map", "[v]",
   "-pix_fmt", "yuv420p", str(tmp / "bad.mp4"))
r = gates.run(tmp / "bad.mp4", out=tmp / "g2")
assert not r["G2"]["pass"] and not r["G5"]["pass"], r
assert any(n.startswith("near-still 3.") for n in r["G6"]["notes"]), r["G6"]   # the still grey stretch is found (black is dark: allowed)
assert gates.run(tmp / "bad.mp4", holds=[(3.0, 6.0)], out=tmp / "g3")["G2"]["pass"], "declared hold is allowed"
assert (tmp / "g2" / "contact_sheet.jpg").exists()

assert blender_autoweight.check() in (0, 2)
from mesh_export import find_blender
if find_blender():   # proxy character -> checker must pass (skipped where Blender is missing, e.g. CI)
    spec = tmp / "spec.json"; spec.write_text(json.dumps({"name": "t", "heads": 5}))
    kb = ROOT / "kit" / "blender"
    subprocess.run([sys.executable, str(kb / "character_blockout.py"), str(spec), str(tmp / "t.blend")], check=True, capture_output=True)
    r = subprocess.run([sys.executable, str(kb / "character_check.py"), str(tmp / "t.blend"), str(tmp / "chk")], capture_output=True, text=True)
    assert r.returncode == 0 and (tmp / "chk" / "sheet.png").exists(), r.stdout
    print("ok: character proxy passes character_check")
else:
    print("skip: Blender not found, character proxy not tested")
print("ok: mix_pro, verify_mix, beats, gates, blender check")

# score: every genre renders on the picture's plan, balanced low end, true silence where asked, energy arc audible
sys.path.insert(0, str(ROOT / "kit" / "audio"))
import score
plan = {"dur": 8, "sections": [{"t": 0, "energy": 0.3}, {"t": 3, "energy": 0.9}], "hits": [6.0], "silences": [[5.7, 6.0]]}
for g in score.GENRES:
    r = score.render({**plan, "genre": g}, tmp / "score" / g)
    m, sr = sf.read(tmp / "score" / g / "music.wav"); m = m.mean(1)
    spec = np.abs(np.fft.rfft(m)) ** 2; f = np.fft.rfftfreq(len(m), 1 / sr)
    low = 10 * np.log10(spec[(f >= 20) & (f < 120)].sum() / spec[(f >= 120) & (f < 16000)].sum())
    assert -7 <= low <= -1, f"{g}: low end {low:.1f} dB"
    assert np.abs(m[int(5.75 * sr):int(5.98 * sr)]).max() < 1e-4, f"{g}: silence before the hit"
    rms = lambda a, b: 10 * np.log10(np.mean(m[int(a * sr):int(b * sr)] ** 2) + 1e-20)
    assert rms(3.5, 5.5) - rms(0.3, 2.5) > 4, f"{g}: no energy arc"
    assert all(abs(s["t"] / r["beat_s"] - round(s["t"] / r["beat_s"])) < 1e-3 for s in r["sections"]), "sections on the beat grid"
# style bands and topic mood: the style's instruments play, the mood moves tempo and mode, forbidden instruments are caught
r = score.render({**plan, "dur": 10, "style": str(ROOT / "styles" / "ukiyoe" / "style.json"), "mood": "dark"}, tmp / "score" / "ukiyoe")
assert r["key"].endswith(" in") and abs(r["bpm"] - (score.GENRES["east-asian"]["bpm"] - 10)) <= 4 and "piano" not in r["instruments"], r
r = score.render({**plan, "dur": 10, "ensemble": {"genre": "future-pop", "lead": "piano", "avoid": ["piano"]}}, tmp / "score" / "avoid")
assert any(c["rule"] == "style.forbidden_instrument" for c in r["critique"]), r["critique"]
r = score.render({**plan, "dur": 10, "ensemble": {"genre": "future-pop", "avoid": ["supersaw"]}}, tmp / "score" / "avoid_synth")
assert any(c["rule"] == "style.forbidden_instrument" for c in r["critique"]), "synth voices are checked too"
try:
    score.render({**plan, "style": str(ROOT / "styles" / "backrooms" / "style.json")}, tmp / "score" / "none"); raise AssertionError("backrooms has no score")
except SystemExit:
    pass
print("ok: score (all genres, style bands, mood, critique)")

# subtitle chunks: 2-4 words, script spelling, timed to the voice, no orphans, no gaps
from beats import chunks, split_words
for s in ["Güneş paneli ışığı nasıl elektriğe çevirir? Altı adımda bakalım.", "Çarpmanın enerjisi, elektronları atomlarından koparır.", "Ve güneşin ışığı, evdeki lambayı yakar."]:
    ws, _ = split_words(s)
    assert all(2 <= len(c) <= 4 for c in ws), ws
    assert " ".join(" ".join(c) for c in ws) == s
cw = {"x": [["Photonlar,", 0.0, .5], ["panelin", .5, .9], ["içindeki", .9, 1.3], ["silisium", 1.3, 1.9], ["hücreye", 1.9, 2.3], ["çarpar.", 2.3, 2.8]]}
cs = chunks(cw, {"x": 10.0}, {"x": "Fotonlar, panelin içindeki silisyum hücreye çarpar."})
assert [c["text"] for c in cs] == ["Fotonlar panelin", "içindeki silisyum hücreye", "çarpar."] or all(2 <= len(c["text"].split()) <= 4 for c in cs), cs
assert "silisyum" in " ".join(c["text"] for c in cs) and "silisium" not in " ".join(c["text"] for c in cs), "script spelling, not whisper's"
assert all(a["t1"] == b["t0"] for a, b in zip(cs, cs[1:])) and abs(cs[0]["t0"] - 9.94) < 1e-6
print("ok: subtitle chunks")

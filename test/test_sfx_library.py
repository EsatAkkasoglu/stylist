"""Indexer sanity: a synthesized click and riser must read as different characters.  python test/test_sfx_library.py"""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from sfx_library import SR, features, role_of, character

rng = np.random.default_rng(0)
t = np.arange(int(0.08 * SR)) / SR
click = (rng.standard_normal(len(t)) * np.exp(-t / 0.004) + np.sin(2 * np.pi * 4000 * t) * np.exp(-t / 0.01)).astype(np.float32)
t2 = np.arange(int(2.0 * SR)) / SR
riser = (np.sin(2 * np.pi * (200 + 600 * t2) * t2) * (t2 / 2.0) ** 2).astype(np.float32)   # rising pitch, slow swell
thud = (np.sin(2 * np.pi * 60 * t2[: SR // 2]) * np.exp(-t2[: SR // 2] / 0.1)).astype(np.float32)

c, r, d = features(click), features(riser), features(thud)
print("click", c, "\nriser", r, "\nthud ", d)
assert c["duration_ms"] < 120 < 1900 < r["duration_ms"]
assert c["attack_ms"] < 15 < 400 < r["attack_ms"], "attack must separate a click from a riser"
assert c["spectral_centroid_hz"] > 2000 > 500 > d["spectral_centroid_hz"], "brightness must separate a click from a sub thud"
assert role_of(["untitled"], c) == "UI/CLICK" and role_of(["untitled"], r) == "DESIGNED/RISER"
assert role_of(["Deep Whoosh #1"], r) == "WHOOSH/SWISH"
assert role_of(["building tension before a drop"], r) == "DESIGNED/RISER", "'building' must not match 'ui'"
assert role_of(["Impact", "impact", "passing car"], r) == "IMPACT/HIT", "title outranks tags"
assert character(d)[0] == "dark/sub" and character(c)[0] == "bright"
print("ok")

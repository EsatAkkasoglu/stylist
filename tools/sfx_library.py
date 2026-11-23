"""Local SFX library: download CC0 sounds, then index them by acoustic character.

  uv run --no-project python tools/sfx_library.py fetch whoosh click impact riser   # Openverse (cc0/pdm, Freesound) + Lots of Sounds samples, then index
  uv run --no-project python tools/sfx_library.py index                              # re-index what is already in sfx_library/
(needs numpy in the project's .venv and ffmpeg on PATH)

Writes sfx_library/files/*, sfx_library/sources.json (where each file came from),
sfx_library/credits.txt and sfx_library/sfx_catalog.json (what the MCP router searches).
"""
import json, re, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path
import numpy as np

LIB = Path(__file__).resolve().parent.parent / "sfx_library"
FILES, SOURCES, CATALOG, CREDITS = LIB / "files", LIB / "sources.json", LIB / "sfx_catalog.json", LIB / "credits.txt"
UA = {"User-Agent": "sfx-router/0.1"}
SR = 22050

# UCS-style role from words in title/tags/query. First match wins, so specific roles come first.
ROLES = [
    ("UI/CLICK", ["click", "tick", "tap", "button", "ui", "beep", "blip", "select"]),
    ("DESIGNED/RISER", ["riser", "rise", "build", "tension", "swell", "rewind"]),
    ("WHOOSH/SWISH", ["whoosh", "swoosh", "swish", "swosh", "woosh", "swipe", "pass"]),
    ("IMPACT/HIT", ["impact", "hit", "punch", "thud", "slam", "boom", "bang", "drop", "stomp"]),
    ("DESIGNED/CHIME", ["chime", "bell", "ding", "success", "notification", "reward"]),
    ("FOLEY/PAPER", ["paper", "page", "book"]),
    ("FOLEY/DOOR", ["door", "knock"]),
    ("FOLEY/MECHANICAL", ["mechanical", "machine", "gear", "switch", "metal", "clank", "spring", "ratchet", "latch"]),
    ("DESIGNED/ALERT", ["siren", "alarm", "alert", "horn"]),
    ("AMBIENCE", ["ambience", "ambient", "birds", "wind", "rain", "room", "city", "crowd", "forest"]),
]


def get_json(url, tries=4):
    for i in range(tries):  # anonymous Openverse answers bursts with a 500 rather than a 429
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                print(f"giving up on {url}: {e}", file=sys.stderr)
                return {}
            time.sleep(4 * (i + 1))


def download(url, dest):
    if dest.exists():
        return True
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            dest.write_bytes(r.read())
        return True
    except Exception as e:  # one dead link must not stop the batch
        print(f"skip {url}: {e}", file=sys.stderr)
        return False


def fetch(queries, per_query=8, max_ms=8000):
    FILES.mkdir(parents=True, exist_ok=True)
    src = json.loads(SOURCES.read_text("utf8")) if SOURCES.exists() else {}
    # Openverse: `category=sound_effect` returns nothing for Freesound items (their category is empty), so filter by licence only.
    for q in queries:
        time.sleep(2)
        url = "https://api.openverse.org/v1/audio/?" + urllib.parse.urlencode({"q": q, "license": "cc0,pdm", "page_size": per_query * 2})
        got = 0
        for r in get_json(url).get("results", []):
            # API only filters coarse length buckets, so exact ms here. Freesound only: other sources are
            # music (Jamendo) or spoken word (Wikimedia pronunciations), not effects.
            if got >= per_query or r.get("source") != "freesound" or not r.get("duration") or r["duration"] > max_ms:
                continue
            got += 1
            fid = f"ov_{r['id'][:8]}"
            name = f"{fid}.{r.get('filetype') or 'mp3'}"
            if download(r["url"], FILES / name):
                src[fid] = {"file": name, "title": r.get("title", ""), "tags": [t["name"] for t in r.get("tags") or []],
                            "query": q, "license": r["license"], "source": f"openverse/{r.get('source')}",
                            "attribution": r.get("attribution", "")}
    # Lots of Sounds: the keyless sample endpoint returns a fixed handful of CC0 sounds.
    base = "https://api.lotsofsounds.com"
    for s in get_json(base + "/api/v1/sounds/sample").get("data", []):
        fid = f"los_{s['id']}"
        if s["duration"] * 1000 > max_ms or (FILES / f"{fid}.mp3").exists():
            continue
        signed = get_json(base + s["stream_url"]).get("data", {}).get("stream_url")   # the stream endpoint answers with a signed, expiring URL
        if signed and download(signed, FILES / f"{fid}.mp3"):
            src[fid] = {"file": f"{fid}.mp3", "title": s["name"], "tags": s.get("tags", []), "query": "", "description": s.get("description", ""),
                        # the API gives no per-file licence; their terms ask for credit, so don't treat these as credit-free
                        "license": "lotsofsounds", "source": "lotsofsounds", "attribution": f'"{s["name"]}" from lotsofsounds.com'}
    SOURCES.write_text(json.dumps(src, indent=1, ensure_ascii=False), "utf8")
    CREDITS.write_text("\n".join(sorted(v["attribution"] for v in src.values() if v["attribution"] and (FILES / v["file"]).exists())) + "\n", "utf8")
    index()


def decode(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.float32)


def features(x):
    """The numbers Claude can't hear but can read: length, brightness, spread, loudness, how fast it hits."""
    dur = len(x) / SR * 1000
    n, hop = 2048, 512
    frames = np.lib.stride_tricks.sliding_window_view(np.pad(x, (0, max(0, n - len(x)))), n)[::hop]
    spec = np.abs(np.fft.rfft(frames * np.hanning(n), axis=1)).sum(0)
    f = np.fft.rfftfreq(n, 1 / SR)
    tot = spec.sum() or 1.0
    centroid = float((f * spec).sum() / tot)
    rolloff = float(f[np.searchsorted(np.cumsum(spec), 0.85 * tot)])
    bandwidth = float(np.sqrt(((f - centroid) ** 2 * spec).sum() / tot))
    rms_db = float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9))
    peak = float(np.abs(x).max()) if len(x) else 0.0
    # attack: from first crossing 10 % of peak envelope to the peak (envelope = 64-sample RMS, ~3 ms)
    h = 64
    env = np.sqrt(np.mean(x[: len(x) // h * h].reshape(-1, h) ** 2, axis=1)) if len(x) >= h else np.abs(x)
    pk = int(env.argmax())
    start = int(np.argmax(env >= 0.1 * env[pk]))
    attack = (pk - start) * h / SR * 1000
    # start_offset: leading silence before the sound (first envelope frame within 40 dB of the peak); mix_pro skips it
    offset = int(np.argmax(env >= env[pk] * 0.01)) * h / SR * 1000
    # active RMS: only envelope frames within 20 dB of the peak, so a 50 ms click in a 3 s file isn't read as quiet
    act = env[env >= env[pk] * 0.1]
    return {"duration_ms": round(dur), "spectral_centroid_hz": round(centroid), "spectral_rolloff_hz": round(rolloff),
            "spectral_bandwidth_hz": round(bandwidth), "rms_db": round(rms_db, 1),
            "active_rms_db": round(float(20 * np.log10(np.sqrt(np.mean(act ** 2)) + 1e-9)), 1),
            "peak_db": round(float(20 * np.log10(peak + 1e-9)), 1), "clipped": bool((np.convolve(np.abs(x) >= 0.98, np.ones(8), "valid") >= 8).any()),   # a flat top (8+ samples pinned), not a normalised peak
            "attack_ms": round(attack, 1), "start_offset_ms": round(offset, 1)}


def role_of(words, ft):
    for w in words:   # most telling first (title, then search word, then tags): an "Impact" tagged "pass" is an impact
        w = w.lower()
        for role, keys in ROLES:
            if any(re.search(rf"\b{k}", w) for k in keys):   # word start, so "building" isn't "ui"
                return role
    # ponytail: keyword + two-feature fallback; swap for a real classifier if roles come out wrong often
    if ft["duration_ms"] < 400 and ft["attack_ms"] < 15:
        return "UI/CLICK"
    if ft["attack_ms"] > 400:
        return "DESIGNED/RISER"
    return "MISC"


def character(ft):
    c = ft["spectral_centroid_hz"]
    tone = "dark/sub" if c < 1200 else "warm" if c < 3000 else "bright"
    hit = "sharp transient" if ft["attack_ms"] < 20 else "soft onset" if ft["attack_ms"] < 150 else "slow swell"
    return tone, f"{tone}, {hit}, {ft['duration_ms']} ms"


def index():
    src = json.loads(SOURCES.read_text("utf8")) if SOURCES.exists() else {}
    cat = []
    for fid, m in src.items():
        p = FILES / m["file"]
        try:
            ft = features(decode(p))
        except Exception as e:
            print(f"cannot index {p.name}: {e}", file=sys.stderr)
            continue
        tone, desc = character(ft)
        cat.append({"id": fid, "path": f"files/{p.name}",   # relative to sfx_library/; the router resolves it
                    "title": m["title"], "description": m.get("description", ""), "tags": m["tags"],
                    "role": role_of([m["title"], m["query"], " ".join(m["tags"])], ft), "brightness": tone,
                    "character": desc, **ft, "license": m["license"], "source": m["source"], "attribution": m["attribution"]})
    CATALOG.write_text(json.dumps(cat, indent=1, ensure_ascii=False), "utf8")
    print(f"{len(cat)} sounds indexed -> {CATALOG}")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["index"]
    fetch(args or ["whoosh", "click", "impact", "riser", "chime", "paper", "swipe"]) if cmd == "fetch" else index()

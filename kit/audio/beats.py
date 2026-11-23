"""Word timings → frames where on-screen type should land (0–2 frames before the word), and short subtitle chunks.

  python beats.py voices/words.json line_starts.json beats.json [--fps 24] [--lead 1]
                  [--lines voices/lines.json --chunks subs.json]

words.json: what lemo's core/tts/asr_check.py writes: {line_id: [[word, start_s, end_s], …]}, times within the line.
line_starts.json: {line_id: seconds where that line starts in the film} (your timeline).
beats.json: [{"line", "word", "t", "frame", "end_frame"}], sorted; "frame" already includes the lead.
subs.json (--chunks): [{"line", "t0", "t1", "text"}]: 2–4 words at a time, timed to the voice, spelt as in the SCRIPT
(lines.json "text", not what whisper heard). Viewers read a short chunk at a glance; a full sentence on screen is too much.
"""
import argparse, json, math, re


def beats(words, starts, fps=24, lead=1):
    out = []
    for lid, ws in words.items():
        if lid not in starts:
            continue
        for w, s, e in ws:
            t = starts[lid] + max(0.0, s)
            out.append({"line": lid, "word": w, "t": round(t, 3),
                        "frame": max(0, math.floor(t * fps) - lead), "end_frame": math.ceil((starts[lid] + e) * fps)})
    return sorted(out, key=lambda b: b["t"])


def split_words(script, lo=2, hi=4):
    """Script words → chunks of lo..hi words, breaking after punctuation when the chunk is long enough; no orphan word."""
    ws = script.split()
    segs, cur = [], []                                          # phrases between punctuation marks
    for i, w in enumerate(ws):
        cur.append(i)
        if re.search(r"[,.;:?!]$", w): segs.append(cur); cur = []
    if cur: segs.append(cur)
    merged = []                                                 # a one-word phrase joins its neighbour
    for s in segs:
        if merged and (len(s) < lo or len(merged[-1]) < lo): merged[-1] += s
        else: merged.append(s)
    out = []
    for s in merged:                                            # balanced pieces, the shorter ones first: "serbest elektronları hep / aynı yöne iter."
        k = math.ceil(len(s) / hi); base, extra = divmod(len(s), k)
        sizes = [base] * (k - extra) + [base + 1] * extra; j = 0
        for z in sizes: out.append(s[j:j + z]); j += z
    return [[ws[i] for i in c] for c in out], out


def chunks(words, starts, scripts, lo=2, hi=4, tail=.4):
    out = []
    for lid, script in scripts.items():
        if lid not in starts or lid not in words:
            continue
        ws, idx = split_words(script, lo, hi)
        tw = words[lid]; n = len(script.split())
        at = lambda i: tw[min(len(tw) - 1, round(i * (len(tw) - 1) / max(1, n - 1)))] if len(tw) != n else tw[i]   # same count: 1:1
        line = []
        for c, ii in zip(ws, idx):
            s, e = at(ii[0])[1], at(ii[-1])[2]
            line.append({"line": lid, "t0": round(starts[lid] + max(0.0, s) - .06, 3), "t1": round(starts[lid] + e, 3), "text": " ".join(c).rstrip(",;:")})
        for a, b in zip(line, line[1:]):
            a["t1"] = b["t0"]                                    # chunks hand over without a gap
        line[-1]["t1"] = round(line[-1]["t1"] + tail, 3)
        out += line
    return sorted(out, key=lambda c: c["t0"])


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("words"); a.add_argument("starts"); a.add_argument("out")
    a.add_argument("--fps", type=float, default=24); a.add_argument("--lead", type=int, default=1, choices=[0, 1, 2])
    a.add_argument("--lines"); a.add_argument("--chunks")
    a = a.parse_args()
    W, S = json.load(open(a.words, encoding="utf8")), json.load(open(a.starts, encoding="utf8"))
    b = beats(W, S, a.fps, a.lead)
    json.dump(b, open(a.out, "w", encoding="utf8"), indent=0, ensure_ascii=False)
    print(f"{len(b)} beats -> {a.out}")
    if a.chunks:
        L = {l["id"]: l["text"] for l in json.load(open(a.lines, encoding="utf8"))}
        c = chunks(W, S, L)
        json.dump(c, open(a.chunks, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        print(f"{len(c)} subtitle chunks -> {a.chunks}")

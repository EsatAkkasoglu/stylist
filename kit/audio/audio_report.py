"""Measure a music file you can't listen to: band balance, level per section, silences, peaks.
   python tools/audio_report.py music.wav [section_starts_s ...]"""
import sys
import numpy as np, soundfile as sf

x, sr = sf.read(sys.argv[1]); x = x.mean(1) if x.ndim > 1 else x
db = lambda v: 10 * np.log10(v + 1e-20)
spec = np.abs(np.fft.rfft(x)) ** 2; f = np.fft.rfftfreq(len(x), 1 / sr)
bands = {"sub 20-60": (20, 60), "bass 60-120": (60, 120), "low-mid 120-500": (120, 500), "mid 500-2k": (500, 2000),
         "presence 2-6k": (2000, 6000), "air 6-16k": (6000, 16000)}
tot = spec[(f > 20) & (f < 16000)].sum()
print("band share (dB of total):", {k: round(db(spec[(f >= a) & (f < b)].sum() / tot), 1) for k, (a, b) in bands.items()})
low = spec[(f >= 20) & (f < 120)].sum(); rest = spec[(f >= 120) & (f < 16000)].sum()
print(f"20-120 Hz vs rest: {db(low / rest):+.1f} dB  (lemo aim: about -3)")
cuts = [0.0] + [float(a) for a in sys.argv[2:]] + [len(x) / sr]
for a, b in zip(cuts, cuts[1:]):
    s = x[int(a * sr):int(b * sr)]
    print(f"{a:6.2f}-{b:6.2f} s  RMS {db(np.mean(s ** 2)):6.1f} dB  peak {20 * np.log10(np.abs(s).max() + 1e-12):6.1f} dBFS")
w = int(0.05 * sr); e = np.array([np.mean(x[i:i + w] ** 2) for i in range(0, len(x) - w, w)])
sil = np.where(db(e) < -70)[0]
print("silent 50 ms windows at (s):", [round(i * 0.05, 2) for i in sil][:20])

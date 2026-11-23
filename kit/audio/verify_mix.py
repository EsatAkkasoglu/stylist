"""Look at the mix, since you can't listen: waveform with red cue lines + the frames either side of each cue.

  python verify_mix.py mix.wav mix_report.json out_dir/verify [--video film.mp4] [--fps 24]

mix_report.json is what mix_pro.py writes (cue start times). Writes verify/waveform.png and, with --video,
verify/cue_<t>_before.png / _after.png (one frame each side). Open them and check every sound sits on its visual change.
"""
import argparse, json, subprocess
from pathlib import Path

W, H = 1920, 240


def duration(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True).stdout)


def verify(mix, report, out, video=None, fps=24):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    times = [c["start_s"] for c in json.loads(Path(report).read_text("utf8"))["cues"]]
    dur = duration(mix)
    lines = ",".join(f"drawbox=x={int(t / dur * W)}:y=0:w=2:h={H}:color=red@0.9:t=fill" for t in times) or "null"
    # dark background: showwavespic draws on transparency, and a white wave on a white viewer is invisible
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mix), "-f", "lavfi", "-i", f"color=c=0x101418:s={W}x{H}", "-filter_complex",
                    f"[0:a]showwavespic=s={W}x{H}:split_channels=0:colors=white[w];[1:v][w]overlay=format=auto,{lines}",
                    "-frames:v", "1", str(out / "waveform.png")], check=True)
    shots = []
    if video:
        for t in times:
            for tag, tt in (("before", t - 1 / fps), ("after", t + 1 / fps)):
                p = out / f"cue_{t:.3f}_{tag}.png"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, tt):.4f}", "-i", str(video), "-frames:v", "1", str(p)], check=True)
                shots.append(p.name)
    return {"waveform": str(out / "waveform.png"), "cues": len(times), "frames": shots}


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("mix"); a.add_argument("report"); a.add_argument("out")
    a.add_argument("--video"); a.add_argument("--fps", type=float, default=24)
    a = a.parse_args()
    r = verify(a.mix, a.report, a.out, a.video, a.fps)
    print(f"{r['waveform']} ({r['cues']} cues), {len(r['frames'])} cue frames. Now look at them.")

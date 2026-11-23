# Sound: voice, SFX, ducking, loudness

You can't hear. Pick sounds by the numbers `search_sfx` returns, place them by frame, and check the result with your eyes (waveform + frames). The library's own tools already do part of this: `core/audio/sfx.py` (procedural foley), `core/tts/` (voice + speech check), `core/render/mux.sh` (two-pass loudnorm to −14 LUFS, true peak ≤ −1 dBTP). Use them; this guide adds what they don't.

## Order

1. Voice first (`core/tts/tts.py`, then `asr_check.py`). Write VO at ~2.5–3 words/s in short beats.
2. Word timings → `vo.words.json`. On-screen type or emphasis lands **0–2 frames before** its word.
3. `cue_sheet.json`: one entry per visual event → `{t_ms, frame, role, want, level_db}`.
4. For each cue call `search_sfx` (role + brightness + onset + max_ms). Pass the ids you already placed in `exclude_ids` when you want a different take.
5. Nothing fits, or you need an exact length (a riser that lasts exactly 18 frames): synthesize with `core/audio/sfx.py` instead.
6. Mix (below), then `sh core/render/mux.sh video.mp4 mix.wav film.mp4`. Don't normalise yourself: mux.sh does it.

The kit does steps 2, 6 and the checks for you (`get_kit`, save into the project's `tools/`): `audio/beats.py` (words.json → frames with lead), `audio/mix_pro.py` (cue sheet → frame-locked, varied, levelled SFX bus + music ducked under voice → `mix.wav`; a `"synth"` cue uses lemo's `sfx.py`), `audio/verify_mix.py` (waveform with cue lines + before/after frames). Everything below is what those scripts do, for when you need to do it by hand.

## Picking by character

| Scene says | role | brightness | onset | length |
|---|---|---|---|---|
| soft UI tap, card select | UI/CLICK | warm | sharp | < 150 ms |
| hard, metallic, mechanical | UI/CLICK or FOLEY/MECHANICAL | bright | sharp | short |
| camera move, card fly-in | WHOOSH/SWISH | warm or bright | soft or swell | ≈ the move's length |
| build-up before a reveal | DESIGNED/RISER | any | swell | ends on the reveal frame |
| big reveal, logo slam | IMPACT/HIT | dark/sub | sharp | 300–1500 ms |
| success, reward, CTA | DESIGNED/CHIME | bright | sharp | < 1 s |
| page turn, paper | FOLEY/PAPER | warm | soft | — |

`brightness` comes from spectral centroid (dark/sub < 1.2 kHz < warm < 3 kHz < bright). `onset` from attack time (sharp < 20 ms < soft < 150 ms < swell).

## Placement (frame-locked)

- `delay_ms = frame / fps * 1000` → `adelay=delay_ms|delay_ms`.
- UI clicks: on the press frame, or **1 frame early**.
- Whoosh: its loudest point on the camera's **fastest** frame (not its start).
- Big reveal: leave **3–8 frames of silence** right before the impact.
- 3–4 sound families per film (clicks, whooshes, one chime, one main impact). Never the same file twice in a row. Each trigger: rate ×0.96–1.04 and gain ±2 dB: `aresample=48000,asetrate=48000*1.03,aresample=48000,volume=1.5dB`. The first `aresample` matters: most library files are 44.1 kHz, and `asetrate=48000*…` on them shifts pitch ~12 %, not 3 %.
- Two ways to lay the cues: the library's own numpy buffer (`core/audio/sfx.py` → `add(buf, x, at_seconds, gain, pan)`; decode a library file to 48 kHz mono float first), or one ffmpeg `adelay` per cue summed with `amix=normalize=0` into `sfx_bus.wav`. Either way, ducking below runs on the stems.

## Levels, relative to the music bed

small click **+3 dB** · whoosh / card move **+4 dB** · main action / chime **+6 dB** · big opening hit **+8 dB** (the loudest moment of the film).

## Ducking (music under voice) — measured, not guessed

The library has a compressor and limiter (`sfx.py` `compress`, `limit`) but no sidechain ducking; use this.

Measure the voice first: `ffmpeg -i vo.wav -af volumedetect -f null -` → `mean_volume` (dB, typically about −26).

**threshold = 10^((mean_volume − 15) / 20)**, ratio 6 → about 12 dB of ducking. (Tested with ffmpeg 7: a fixed `threshold=0.08` gives **0 dB** of ducking on a −26 dB voice.)

```sh
ffmpeg -i music.wav -i vo.wav -i sfx_bus.wav -filter_complex "
[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[mus];
[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asplit=2[sc][vox];
[mus][sc]sidechaincompress=threshold=<TH>:ratio=6:attack=15:release=350[duck];
[2:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[fx];
[duck][vox][fx]amix=inputs=3:duration=longest:normalize=0[out]" -map "[out]" -c:a pcm_s24le mix.wav
```

- Music is the **first** input of `sidechaincompress`; the voice drives it through `[sc]` and is heard through `[vox]`.
- Both streams are made 48 kHz stereo float first; mono TTS against stereo music otherwise mixes wrong without an error.
- attack 5–20 ms (40 ms for slow presentations); 0 ms clips consonants. release 350 ms avoids pumping.
- Podcast-style delivery: tell mux.sh's caller to aim −16 LUFS instead (edit the copy in the project, never `core/`).

## Check (you can't listen, so look)

- `ffmpeg -i mix.wav -filter_complex "showwavespic=s=1920x240:split_channels=0" verify/waveform.png`; draw each cue time as a red line (`drawbox` or Pillow) and look at it.
- For each cue, the frames before and after: `ffmpeg -ss <t-1/fps> -i film.mp4 -frames:v 1 verify/cue_<t>_before.png` and `… <t+1/fps> … _after.png`. The sound must sit on the visual change.
- mux.sh prints the measured I / LRA / true peak: −14 ±1 LUFS, peak ≤ −1 dB.

## Licence

Every library sound carries `license` and `attribution`. Prefer cc0/pdm (no credit needed). For anything else (including `lotsofsounds`), copy its `attribution` line into the film's credits file. `sfx_library/credits.txt` lists them all.

## Browser preview (Web Audio), if you build one

Start nodes 100–150 ms early at gain 0.001; ramps ≥ 50 ms on low frequencies; `exponentialRampToValueAtTime` to 0.001, never 0, then stop. Otherwise you get clicks and pops.

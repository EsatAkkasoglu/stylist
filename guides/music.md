# Music: original, made by you, in the style's band and the topic's mood

Customers judge a film by its sound first. Three failures we have already shipped and must not repeat:
- **no music at all**: a film delivered with SFX only;
- **music too loud against the voice**;
- **generic "film music"** (piano and strings) where the style asks for something else.

## Always make the music

Every film gets an original score, **without being asked**. Leave it out only when the customer says so (`build_brief` `music: "none"`) or when the style has no score (`backrooms`: its music lives only inside the world).

You **write the music as notes** and a renderer plays them. Each style says which one (style.json `stylist.score.render.engine`):

| Engine | Styles | Kit | Sound |
|---|---|---|---|
| `notes` | acoustic, orchestral, jazz, folk, mallets (most styles) | `audio/notes.py` | MusicXML + MIDI, played by FluidSynth with the MuseScore General soundfont (or the MuseScore CLI); `hall` or `dry` master |
| `synth` | synthwave, HUD, dataviz, chiptune, city pop, electronic news | `audio/synth.py` | Surge XT factory patches inside DawDreamer; `neon` or `dry` master |

Both read the same `cue.json` and run headless on a server (`sh kit/setup_server.sh`, `WITH_SURGE=1` for synth). Before you say a tool is missing, run it end to end. `audio/score.py` (generated arrangement) is only a fallback when neither renderer can be installed.

## Who decides what

| Decides | What | Where |
|---|---|---|
| **The style** | engine, band (a GM program or Surge patch per role: lead, counter, pad, pulse, bass, sparkle), drums, space, own mode, forbidden instruments | style.json `stylist.score` and `stylist.score.render` |
| **The topic** | feeling: bright · playful · warm · calm · wonder · tense · dark · epic → key, mode, tempo, harmony | your `cue.json` |
| **The picture** | bars and sections, energy arc, hits, silence | your `cue.json` |
| **The customer** | another groove (`music: "<genre>"`, still the style's band) or none | `build_brief` |

The groove reference (`genre`) tells you the rhythm language to write in:

| Genre | Groove |
|---|---|
| `cinematic-pulse` | strings and pulse |
| `future-pop` | four on the floor |
| `lofi-chill` | swung keys |
| `synthwave` | arps and gated snare |
| `ambient-wonder` | swells, no kit |
| `chiptune` | pulse, triangle and noise |
| `jazz-combo` | walking bass and brushes |
| `hot-jazz` | stride piano, banjo on 2 & 4, two-beat bass |
| `minimal-pulse` | Reich-style mallets |
| `folk-acoustic` | strum and cajon |
| `chamber-march` | staccato ostinato and snare |
| `baroque-motor` | harpsichord 16ths and canon |
| `east-asian` | pentatonic plucks and frame drum |
| `drone-sparse` | held low strings and single notes |
| `city-pop` | slap bass, FM keys, sax |
| `rock-opening` | power chords |

A style's band changes in `tools/style_scores.json` (instruments) and `tools/import_styles.py` (`VOICE`, `GENRE_BAND`), then `python tools/import_styles.py --relayer`.

## Writing the notes

`cue.json` (format in the kit file's docstring): one part per band role, each `[pitch | [chord] | null, beats, velocity]`, all parts the same length. Proven examples: `demo/art-deco-score/cue.json` (notes) and `demo/hud-synthwave/cue.json` (synth).

- **Bars first.** Length = bars × 4 × 60 / BPM. Pick the BPM so section starts fall on bar lines at the picture's cuts.
- **One chord per bar**, a progression from the genre (hot jazz I–VI7–II7–V7; synthwave i–VI–III–VII). The lead's strong beats sit on chord tones.
- **One motif.** State it, let a second voice answer or take it over, raise it at the climax (octave up, thirds with the counter), end on the tonic.
- **Texture is the arc.** Instruments enter one at a time: intro (pad, pulse) → groove (bass, drums) → melody → tutti → ending. The intro sits about 6–9 dB under the climax through velocity and density.
- **Comping keeps time** where there are no drums: stride piano (bass note on 1 & 3, chord on 2 & 4), banjo on 2 & 4, 16th arps.
- **Velocity is phrasing:** downbeats 80–100, offbeats 60–75, climax 95–110.
- **Ending:** `button` (one short tutti stab, then rests) for punchy ads; a held chord for warm endings.
- **One real silence** (0.25–0.5 s) right before the payoff hit.
- Synth drums: Surge percussion patches are pitched: play the kick on C3 and the snare on D3.

## Write the music plan before animating (lemo DIRECTOR §7)

Write the cue's sections from the shot list: the hook, the cuts, the payoff and the energy at each.

- **Energy arc, not a flat loop**: intro 0.2–0.4 → lift 0.7–0.9 on the first cut → a breath 0.4–0.6 → 1.0 on the payoff.
- **Cut on the grid.** Take cuts and key actions from the bar and beat grid (beat = 60 / BPM s).
- **Hits**: the payoff and at most one more.

## Level

`kit/audio/mix_pro.py`:
- **With a voice**, the music bed is staged against the speaking level:
  - between lines: about **10 dB under** (`--music-vs-vo -10`; -8 for music-led films, -14 for dense explainers);
  - under speech: about **20–25 dB under** (sidechain);
  - check `measured`.
- **Without a voice** (music-led ads), the score stays at its own level and the SFX sit on it by role. mux.sh masters to -14 LUFS.

## Check it, since you can't listen

- `python kit/audio/audio_report.py music.wav <section starts…>`:
  - band balance: 20–120 Hz about -3 dB against the rest; 2–6 kHz not under -12 dB;
  - RMS per section: the arc must be visible;
  - silences and peaks.
- `ffmpeg -i music.wav -lavfi showspectrumpic=s=1200x400:scale=log:fscale=log spectrum.png`, then look at it:
  - risers show as rising ramps into cuts;
  - a black gap sits before the hit;
  - hits are full-height columns.
- Say plainly in the delivery note that the score was measured and not heard.

## Credits

The MuseScore General soundfont (notes) and Surge XT (synth, GPL-3, only its sound is in the film) need no credit line. `score.py`'s fallback lists its sample libraries in `music_report.json` → `credits`; Salamander piano and MuldjordKit are CC BY.

# Creative bar: what makes a film not "simple"

Lemo's DIRECTOR.md is the method; this is the bar a customer film has to clear, written as checks you can run. Our first demo failed it: nothing on screen in the first second, half the frame empty paper for 5 s, three shots in 15 s that all looked alike, one camera move.

## 0. Clarity beats cleverness (explainers)

Customer feedback on our demos: "I can't tell what is happening." For any film that explains how something works:

- **One step per shot, one idea per line.** Write the mechanism as numbered steps first (e.g. light → hits the cell → frees electrons → the layers push them one way → direct current → inverter → the lamp). Every step gets its own shot, its own voice line and its own on-screen label.
- **Label what the viewer must understand**, at the moment it happens, near the thing it names (FOTON, ELEKTRON, N / P KATMAN, DOĞRU AKIM). A step number (1/6) helps the viewer keep track.
- **Show cause, then effect, with a beat between.** Don't let the next thing start before the last one has been seen: hold each result ~1 s after it happens.
- **The script says what the picture shows**, in plain words, active voice, one fact per sentence. No poetic lines the picture can't prove, no unexplained jargon, no skipped step (the first demo skipped why electrons flow one way).
- **Subtitles: 2–4 words at a time**, timed to the voice (kit `audio/beats.py --chunks`), one line, large. They must look different from in-scene labels: labels name things in the picture (the style's material), subtitles carry the voice (the style's subtitle rule, never the label's card).
- **Slower than you think**: about 4–5 s per step; a 6-step explainer is 30 s, not 15.
- Style and metaphor come after this, never instead of it.

## 1. Concept before treatment

Write three **concepts** (not structures): each one sentence that names a **visual idea** the topic doesn't obviously suggest. Pick the most surprising one that still explains the topic. Examples for "how a solar panel works":
- *literal*: sun → cell → wire → house (the cliché: avoid as the main idea);
- *scale*: one photon's journey, from 150 million km away to a reading lamp, in one continuous push;
- *metaphor*: electrons as a crowd at a stadium gate that the light opens;
- *reversal*: start at night in the dark house, rewind to where the light came from.

## 2. The checks (run them on the contact sheet, a frame every 1 s)

| # | Check | Fails when |
|---|---|---|
| C1 | **Hook in frame 1** | the first frame is empty or a slow build; something must be moving and readable at t=0 |
| C2 | **A new image every 2–3 s** | two tiles 2 s apart look alike (same framing, same subject size) |
| C3 | **Fill the frame** | more than ~40 % of any tile is empty background for more than 1.5 s |
| C4 | **Depth** | no tile has foreground, subject and background at different speeds (parallax, particles, light) |
| C5 | **Scale change** | the film never goes from very close to very wide (or the reverse) |
| C6 | **Four camera moves** | fewer than 4 of: push, pull, track, pan, tilt, orbit, whip, rack focus, parallax drift |
| C7 | **Transitions from the medium** | more than half the cuts are plain hard cuts; use match cuts (shape → shape), morphs, wipes made of the style's own material (ink, paper, light) |
| C8 | **Kinetic type** | text only fades in; type should be part of the motion (built, revealed, pushed by the camera) |
| C9 | **One signature shot** | nothing a viewer would describe to a friend; plan it, give it the score's hit and the silence before it |
| C10 | **Payoff echoes the hook** | the ending doesn't call back to the opening image |
| C11 | **Colour script** | the palette doesn't change with the story (cold → warm, dark → light) within what STYLE.md allows |

Report C1–C11 as pass/fail with the tile numbers, next to gates G0–G6.

## 3. Rhythm with the music

- Shots follow the music plan's energy: short shots in the drop, one long breath before the payoff.
- Visual hits land on the score's hits (frame-exact, from `music_report.json`), never a frame late.
- Sound transitions: at least one J-cut (next scene's sound starts early) and one L-cut.

## 4. Use the style's engine, not a sketch of it

Each lemo style ships a real engine in its demo (brushes, paper shaders, 3D materials, camera rigs). After the treatment, `sh "<skill dir>/scripts/setup.sh" demo <slug>`, read `DEMO.md`, copy the engine files into the project and build the new film on them. A hand-rolled imitation of the style looks cheap next to the gallery, and customers compare.

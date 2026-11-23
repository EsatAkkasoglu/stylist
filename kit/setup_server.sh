#!/bin/sh
# Headless music stack for the Stylist kit on a Debian/Ubuntu x64 server (root, or a user with sudo).
#   sh kit/setup_server.sh                     acoustic / orchestral: kit/audio/notes.py (FluidSynth + MuseScore General soundfont)
#   WITH_SURGE=1 sh kit/setup_server.sh        + electronic: kit/audio/synth.py (Surge XT VST3 inside DawDreamer)
#   WITH_MUSESCORE=1 sh kit/setup_server.sh    + MuseScore 3 CLI (notation/PDF; notes.py falls back to it without FluidSynth)
set -e
SURGE_VERSION=1.3.4
SUDO=$([ "$(id -u)" = 0 ] && echo "" || echo sudo)
$SUDO apt-get update
$SUDO apt-get install -y --no-install-recommends fluidsynth musescore-general-soundfont-small ffmpeg python3-pip curl ca-certificates
if [ "${WITH_MUSESCORE:-0}" = 1 ]; then $SUDO apt-get install -y --no-install-recommends musescore3; fi
python3 -m pip install --upgrade music21 numpy scipy soundfile pedalboard
if [ "${WITH_SURGE:-0}" = 1 ]; then
  deb=/tmp/surge-xt-$SURGE_VERSION.deb
  curl -fsSL -o "$deb" "https://github.com/surge-synthesizer/releases-xt/releases/download/$SURGE_VERSION/surge-xt-linux-x64-$SURGE_VERSION.deb"
  $SUDO apt-get install -y --no-install-recommends "$deb"     # pulls its X11/freetype libs; runs headless, no display needed
  python3 -m pip install --upgrade dawdreamer
  ls "/usr/lib/vst3/Surge XT.vst3" /usr/share/surge-xt/patches_factory >/dev/null
fi
fluidsynth --version | head -1
ls /usr/share/sounds/sf3/

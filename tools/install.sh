#!/bin/bash
# Copy dist/fo1_objectives into the game's mods folder. Keeps settings already in the
# installed objectives.ini (changed in game); only adds new keys/sections from the new one.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$HOME/.steam/debian-installation/steamapps/common/Fallout 2/Fallout1in2/mods/fo1_objectives}"
if pgrep -fi 'fallout2(hr)?\.exe' >/dev/null; then echo "game is running - not installing"; exit 1; fi
mkdir -p "$DEST/scripts"
cp "$ROOT/dist/fo1_objectives/scripts/gl_objectives.int" "$DEST/scripts/"
cp "$ROOT/dist/fo1_objectives/readme.txt" "$DEST/"
cp -r "$ROOT/dist/fo1_objectives/art" "$DEST/"
if [ -f "$DEST/objectives.ini" ]; then
   python3 "$ROOT/tools/merge_ini.py" "$ROOT/dist/fo1_objectives/objectives.ini" "$DEST/objectives.ini"
else
   cp "$ROOT/dist/fo1_objectives/objectives.ini" "$DEST/"
fi
echo "installed to $DEST"

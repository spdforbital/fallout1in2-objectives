#!/bin/bash
# Fetch the readable Fo1in2 script sources (rotators/Fo1in2, scripts + sfall modders pack only)
# into vendor/fo1in2-src, at the commit the quest data was checked against.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT=818f18efdeeea94cd7529d612e906f7cb0777adb
DEST="$ROOT/vendor/fo1in2-src"
if [ ! -d "$DEST/.git" ]; then
   git clone --filter=blob:none --no-checkout https://github.com/rotators/Fo1in2.git "$DEST"
fi
cd "$DEST"
git sparse-checkout set Fallout2/Fallout1in2/Mapper/source/ Tools/ModdersPack Tools/SFallScriptEditor/Descriptions
git checkout "$COMMIT"
echo "Fo1in2 sources in $DEST"
echo "Also put sfall's script compiler (compile.exe, sfall modders pack) in $ROOT/tools/bin/"

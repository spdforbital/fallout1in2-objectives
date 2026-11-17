#!/bin/bash
# Build Fallout 1in2 Objectives: data header, offline tests, gl_objectives.int, dist/fo1_objectives.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 tools/build_data.py
python3 tools/test_data.py
# sslc (sfall 4.5.1 edition) via wine: -p preprocess (mcpp), -s short-circuit and/or, -O2 optimize
cd src
WINEDEBUG=-all wine ../tools/bin/compile.exe -q -l -p -s -O2 \
   '-I..\vendor\fo1in2-src\Tools\ModdersPack\scripting\headers' '-I..\build' \
   gl_objectives.ssl -o '..\build\gl_objectives.int' | tee ../build/compile.log
cd ..
if grep -qiE '\[error\]|errors' build/compile.log; then echo "compile FAILED"; exit 1; fi
rm -rf dist/fo1_objectives
mkdir -p dist/fo1_objectives/scripts
cp build/gl_objectives.int dist/fo1_objectives/scripts/
cp mod/objectives.ini dist/fo1_objectives/
cp mod/readme.txt dist/fo1_objectives/
cp -r mod/art dist/fo1_objectives/
echo "built dist/fo1_objectives"

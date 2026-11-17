#!/usr/bin/env python3
"""merge_ini.py NEW OLD: write NEW's layout (comments, new keys) to OLD, keeping OLD's values."""
import re
import sys

new, old = sys.argv[1], sys.argv[2]
vals, sec = {}, ""
for line in open(old, encoding="latin1"):
    m = re.match(r"\s*\[(.+)\]", line)
    if m:
        sec = m.group(1).strip().lower()
    m = re.match(r"\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", line)
    if m and not line.lstrip().startswith(";"):
        vals[(sec, m.group(1).lower())] = m.group(2)
out, sec = [], ""
for line in open(new, encoding="latin1"):
    m = re.match(r"\s*\[(.+)\]", line)
    if m:
        sec = m.group(1).strip().lower()
    m = re.match(r"(\s*)([A-Za-z0-9_]+)(\s*=\s*)(.*?)(\s*)$", line)
    if m and not line.lstrip().startswith(";") and (sec, m.group(2).lower()) in vals:
        line = m.group(1) + m.group(2) + m.group(3) + vals[(sec, m.group(2).lower())] + "\n"
    out.append(line.rstrip("\r\n"))
open(old, "w", encoding="latin1", newline="\r\n").write("\n".join(out) + "\n")

#!/usr/bin/env python3
"""List GVARs that the Fo1in2 scripts set but no quest data uses, minus obvious bookkeeping.
Helps find tasks that never show in the Pip-Boy and are missing from data/steps.
Known non-quests can be listed in data/coverage_ignore.txt (one GVAR per line, # comments)."""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import objdata as od  # noqa: E402

NOISE = re.compile(
    r"MARK_|WORLDMAP|ENEMY_|REACTION|_KNOWN$|TOWN_REP|KARMA|_DEAD$|_KILLED$|HOSTILE|PLAYER_|"
    r"SLIDE|LOAD|TIMER|TIME|DAYS|INVADED|INVASION|_COUNT|COUNTER|ENABLE|SETTING|CHEAT|SAVE_|"
    r"RND|RANDOM|AREA|MAP_|DOOR|_HIRELING|JOINS_GIVE|FO1IN2|FIXT|PARTY|HAS_|CAR_|MOVIE|"
    r"_SEEN|_MET|TALKED|_ALIVE|IS_DEAD|HOLODISK|SOMETHING|SPECIAL_|DISTANCE_VAL")


def main():
    used = set()
    for f in os.listdir(od.STEPS_DIR):
        used |= set(re.findall(r"GVAR_\w+", od.read_text(os.path.join(od.STEPS_DIR, f))))
    used |= set(re.findall(r"GVAR_\w+", od.read_text(os.path.join(od.ROOT, "src", "gl_objectives.ssl"))))
    ign = os.path.join(od.ROOT, "data", "coverage_ignore.txt")
    if os.path.exists(ign):
        used |= set(re.findall(r"^\s*(GVAR_\w+)", od.read_text(ign), re.M))
    sets = collections.defaultdict(set)
    for root, _, files in os.walk(od.SRC):
        if "headers" in root:
            continue
        for fn in files:
            if fn.lower().endswith(".ssl"):
                text = od.read_text(os.path.join(root, fn))
                for g in re.findall(r"set_global_var\s*\(\s*(GVAR_\w+)", text):
                    sets[g].add(os.path.relpath(root, od.SRC))
    cand = sorted(g for g in sets if g not in used and not NOISE.search(g))
    for g in cand:
        print(g, ",".join(sorted(sets[g])))
    print("%d GVARs set by scripts, %d possibly quest-like and not covered" % (len(sets), len(cand)))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fallout 1in2 Objectives - data model, parsers and validation.

Reads:
  * quests.txt, QUESTS.msg, Vault13.gam, CITY.TXT  (mods/fo1_base of the game)
  * the Fo1in2 script headers (global.h, itempid.h, critpid.h, scenepid.h, scripts.h, maps.h)
  * data/steps/*.txt  (hand-written quest steps, format in data/steps/FORMAT.txt)
and builds an in-memory model (list of quests with steps and compiled conditions).

Used by build_data.py (writes the SSL data header + JSON) and test_data.py.
"""
import os
import re
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.environ.get(
    "FO1IN2_DIR",
    os.path.expanduser("~/.steam/debian-installation/steamapps/common/Fallout 2/Fallout1in2"))
BASE = os.path.join(GAME, "mods", "fo1_base")
SRC = os.path.join(ROOT, "vendor", "fo1in2-src", "Fallout2", "Fallout1in2", "Mapper",
                   "source", "scripts")
HEADERS = os.path.join(SRC, "headers")
STEPS_DIR = os.path.join(ROOT, "data", "steps")

# ---------------------------------------------------------------------------
# Towns / areas / maps
# ---------------------------------------------------------------------------
# town name -> area id (city.txt), used for world map directions
TOWNS = [
    ("Vault 13", 0), ("Vault 15", 1), ("Shady Sands", 2), ("Junktown", 3),
    ("Raiders", 4), ("Necropolis", 5), ("Hub", 6), ("Brotherhood", 7),
    ("Military Base", 8), ("Glow", 9), ("Boneyard", 10), ("Cathedral", 11),
]
TOWN_ORDER = [t for t, _ in TOWNS]

# map name -> (town, short label shown as "go to <label>")
MAP_INFO = {
    "SCRAPHEAP": ("Necropolis", "Scrapheap (motel PC)"),
    "V13ENT": ("Vault 13", "Vault 13 cave"),
    "VAULT13": ("Vault 13", "Vault 13"),
    "VAULTENT": ("Vault 15", "Vault 15 shack"),
    "VAULTBUR": ("Vault 15", "Vault 15"),
    "SHADYW": ("Shady Sands", "Shady Sands west"),
    "SHADYE": ("Shady Sands", "Shady Sands east"),
    "CAVES": ("Shady Sands", "Radscorpion caves"),
    "JUNKENT": ("Junktown", "Junktown gate"),
    "JUNKCSNO": ("Junktown", "Junktown casino"),
    "JUNKKILL": ("Junktown", "Killian's store"),
    "RAIDERS": ("Raiders", "Khans' camp"),
    "HOTEL": ("Necropolis", "Necropolis hotel"),
    "HALLDED": ("Necropolis", "Hall of the Dead"),
    "WATRSHD": ("Necropolis", "Watershed"),
    "VAULTNEC": ("Necropolis", "Necropolis vault"),
    "HUBENT": ("Hub", "Hub entrance"),
    "HUBDWNTN": ("Hub", "Hub downtown"),
    "HUBHEIGT": ("Hub", "Hub heights"),
    "HUBOLDTN": ("Hub", "Hub old town"),
    "HUBWATER": ("Hub", "Water Merchants"),
    "DETHCLAW": ("Hub", "Deathclaw lair"),
    "HUBMIS0": ("Hub", "Irwin's farm"),
    "BROHDENT": ("Brotherhood", "Brotherhood gate"),
    "BROHD12": ("Brotherhood", "Brotherhood L1-2"),
    "BROHD34": ("Brotherhood", "Brotherhood L3-4"),
    "MBENT": ("Military Base", "Military Base"),
    "MBSTRG12": ("Military Base", "Base storage"),
    "MBVATS12": ("Military Base", "The Vats"),
    "GLOWENT": ("Glow", "The Glow"),
    "GLOW1": ("Glow", "Glow levels 1-2"),
    "GLOW2": ("Glow", "Glow levels 3-6"),
    "LAADYTUM": ("Boneyard", "Adytum"),
    "LAFOLLWR": ("Boneyard", "Followers library"),
    "LABLADES": ("Boneyard", "Blades"),
    "LAGUNRUN": ("Boneyard", "Gun Runners"),
    "LARIPPER": ("Boneyard", "Deathclaw nest"),
    "CHILDRN1": ("Cathedral", "Cathedral"),
    "CHILDRN2": ("Cathedral", "Cathedral upstairs"),
    "MSTRLR12": ("Cathedral", "Master's vault"),
    "MSTRLR34": ("Cathedral", "Master's vault"),
}

OPS = {"==": 1, "!=": 2, ">=": 3, "<=": 4, ">": 5, "<": 6}
# condition atom types (each atom = 5 ints: type, a, b, op, c)
C_OR, C_GVAR, C_ITEM, C_MAP, C_MVAR, C_TRUE, C_FALSE, C_TOWN, C_PARTY = 0, 1, 2, 3, 4, 5, 6, 7, 8
# target kinds
T_NONE, T_NPC, T_CRITTER, T_ITEM, T_SCENERY, T_TILE = 0, 1, 2, 3, 4, 5
TARGET_KINDS = {"npc": T_NPC, "critter": T_CRITTER, "item": T_ITEM,
                "scenery": T_SCENERY, "tile": T_TILE}

MAX_STEP_TEXT = 45
MAX_NAME = 32
MAX_NOTE = 70


class DataError(Exception):
    pass


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------
def read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("cp1252")


def find_ci(directory, name):
    """Case-insensitive file lookup."""
    for n in os.listdir(directory):
        if n.lower() == name.lower():
            return os.path.join(directory, n)
    raise FileNotFoundError(os.path.join(directory, name))


def parse_defines(path, prefix):
    out = {}
    for m in re.finditer(r"^\s*#define\s+(" + prefix + r"\w*)\s+\(?\s*(-?\d+)\s*\)?",
                         read_text(path), re.M):
        out[m.group(1)] = int(m.group(2))
    return out


def load_constants():
    c = {}
    c["GVAR"] = parse_defines(os.path.join(HEADERS, "global.h"), "GVAR_")
    pids = {}
    for h in ("itempid.h", "critpid.h", "scenepid.h"):
        pids.update(parse_defines(os.path.join(HEADERS, h), "PID_"))
    c["PID"] = pids
    c["SCRIPT"] = parse_defines(os.path.join(HEADERS, "scripts.h"), "SCRIPT_")
    c["MAP"] = parse_defines(os.path.join(HEADERS, "maps.h"), "MAP_")
    c["AREA"] = parse_defines(os.path.join(HEADERS, "maps.h"), "AREA_")
    return c


def load_gam():
    """Vault13.gam: list index -> name (in file order)."""
    names = []
    for line in read_text(os.path.join(BASE, "data", "Vault13.gam")).splitlines():
        m = re.match(r"\s*(\w+)\s*:=\s*-?\d+\s*;", line)
        if m:
            names.append(m.group(1))
    return names


def load_msg(path):
    out = {}
    txt = read_text(path)
    for m in re.finditer(r"\{(\d+)\}\{[^}]*\}\{([^}]*)\}", txt):
        out[int(m.group(1))] = " ".join(m.group(2).split())
    return out


def load_quests_txt():
    out = []
    for line in read_text(os.path.join(BASE, "data", "quests.txt")).splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split(",")]
        if len(parts) != 5:
            continue
        loc, desc, gvar, disp, comp = map(int, parts)
        out.append(dict(location=loc, pipboy=desc, gvar=gvar, display=disp, completed=comp))
    return out


def load_areas():
    """CITY.TXT area id -> (x, y) world position."""
    out = {}
    cur = None
    for line in read_text(os.path.join(BASE, "data", "CITY.TXT")).splitlines():
        m = re.match(r"\[Area (\d+)\]", line)
        if m:
            cur = int(m.group(1))
            continue
        m = re.match(r"world_pos=(\d+),(\d+)", line.strip())
        if m and cur is not None:
            out[cur] = (int(m.group(1)), int(m.group(2)))
    return out


# ---------------------------------------------------------------------------
# Step files
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self):
        self.const = load_constants()
        self.gam = load_gam()
        self.quests_txt = load_quests_txt()
        self.quest_msg = load_msg(find_ci(os.path.join(BASE, "text", "english", "game"),
                                          "QUESTS.msg"))
        self.areas = load_areas()
        self.errors = []
        self.warnings = []
        self.used = {"GVAR": set(), "PID": set(), "SCRIPT": set(), "MAP": set(), "AREA": set()}

    def err(self, where, msg):
        self.errors.append("%s: %s" % (where, msg))

    def warn(self, where, msg):
        self.warnings.append("%s: %s" % (where, msg))

    # -- constants ---------------------------------------------------------
    def value(self, tok, kind, where):
        """Resolve a constant name or integer. kind in GVAR/PID/SCRIPT/MAP/None."""
        if re.fullmatch(r"-?\d+", tok):
            return int(tok)
        for k in (kind,) if kind else ("GVAR", "PID", "SCRIPT", "MAP"):
            table = self.const.get(k, {})
            if tok in table:
                self.used[k].add(tok)
                return table[tok]
        self.err(where, "unknown constant %r (expected %s)" % (tok, kind or "number"))
        return 0

    def check_gvar(self, num, where, name=None):
        if num < 0 or num >= len(self.gam):
            self.err(where, "GVAR %d out of range (Vault13.gam has %d)" % (num, len(self.gam)))
        elif self.gam[num].startswith("RESERVED"):
            self.err(where, "GVAR %d (%s) is a reserved slot" % (num, name or "?"))

    def check_pid(self, pid, where, kind=None):
        typ = pid >> 24
        if pid <= 0 or typ not in (0, 1, 2, 5):
            self.err(where, "bad PID %d" % pid)
        if kind == T_ITEM and typ != 0:
            self.err(where, "PID %d is not an item" % pid)
        if kind == T_CRITTER and typ != 1:
            self.err(where, "PID %d is not a critter" % pid)
        if kind == T_SCENERY and typ != 2:
            self.err(where, "PID %d is not scenery" % pid)

    def map_num(self, name, where):
        name = name.upper()
        if name.startswith("MAP_"):
            name = name[4:]
        if re.fullmatch(r"\d+", name):
            return int(name)
        key = "MAP_" + name
        if key not in self.const["MAP"]:
            self.err(where, "unknown map %r" % name)
            return -1
        self.used["MAP"].add(key)
        return self.const["MAP"][key]

    # -- conditions --------------------------------------------------------
    def cond(self, text, where):
        """Parse a condition into a flat list of atoms; OR groups separated by C_OR atoms."""
        atoms = []
        groups = [g.strip() for g in text.split("|")]
        for gi, g in enumerate(groups):
            if gi:
                atoms.append([C_OR, 0, 0, 0, 0])
            if not g:
                self.err(where, "empty OR branch in %r" % text)
                continue
            for a in [x.strip() for x in g.split("&")]:
                atoms.append(self.atom(a, where))
        return atoms

    def atom(self, a, where):
        t = a.split()
        if not t:
            self.err(where, "empty condition")
            return [C_FALSE, 0, 0, 0, 0]
        if t == ["true"]:
            return [C_TRUE, 0, 0, 0, 0]
        if t == ["false"]:
            return [C_FALSE, 0, 0, 0, 0]
        if t[0] in ("item", "noitem"):
            if len(t) not in (2, 4):
                self.err(where, "bad item condition %r" % a)
                return [C_FALSE, 0, 0, 0, 0]
            pid = self.value(t[1], "PID", where)
            self.check_pid(pid, where, T_ITEM)
            if t[0] == "noitem":
                if len(t) != 2:
                    self.err(where, "noitem takes no comparison: %r" % a)
                return [C_ITEM, pid, 0, OPS["=="], 0]
            if len(t) == 4:
                if t[2] not in OPS:
                    self.err(where, "bad operator in %r" % a)
                return [C_ITEM, pid, 0, OPS.get(t[2], 3), self.value(t[3], None, where)]
            return [C_ITEM, pid, 0, OPS[">="], 1]
        if t[0] in ("party", "noparty"):
            if len(t) != 2:
                self.err(where, "bad party condition %r (party PID_X)" % a)
                return [C_FALSE, 0, 0, 0, 0]
            pid = self.value(t[1], "PID", where)
            self.check_pid(pid, where, T_CRITTER)
            return [C_PARTY, pid, 0, OPS["!="] if t[0] == "party" else OPS["=="], 0]
        if t[0] == "map":
            if len(t) != 2:
                self.err(where, "bad map condition %r" % a)
            return [C_MAP, self.map_num(t[1], where), 0, 0, 0]
        if t[0] == "town":
            if len(t) != 4 or t[2] not in OPS or not t[1].startswith("AREA_"):
                self.err(where, "bad town condition %r (town AREA_X >= 2)" % a)
                return [C_FALSE, 0, 0, 0, 0]
            return [C_TOWN, self.value(t[1], "AREA", where), 0, OPS[t[2]], int(t[3])]
        if t[0] == "mvar":
            if len(t) != 5 or t[3] not in OPS:
                self.err(where, "bad mvar condition %r" % a)
                return [C_FALSE, 0, 0, 0, 0]
            return [C_MVAR, self.map_num(t[1], where), int(t[2]), OPS[t[3]],
                    self.value(t[4], None, where)]
        if len(t) == 3 and t[1] in OPS:
            g = self.value(t[0], "GVAR", where)
            if not re.fullmatch(r"-?\d+", t[0]) and not t[0].startswith("GVAR_"):
                self.err(where, "expected a GVAR_ name, got %r" % t[0])
            self.check_gvar(g, where, t[0])
            return [C_GVAR, g, 0, OPS[t[1]], self.value(t[2], None, where)]
        self.err(where, "cannot parse condition %r" % a)
        return [C_FALSE, 0, 0, 0, 0]


def strip_comment(line):
    s = line.rstrip("\n")
    if s.lstrip().startswith("#"):
        return ""
    # trailing comments: " # ..." (keywords never contain '#')
    m = re.search(r"\s#\s", s)
    if m:
        s = s[:m.start()]
    return s.strip()


def parse_step_files(ctx, files=None):
    quests = []
    files = files or sorted(f for f in os.listdir(STEPS_DIR)
                            if f.endswith(".txt") and f != "FORMAT.txt")
    for fn in files:
        path = os.path.join(STEPS_DIR, fn)
        q = None
        st = None
        for ln, raw in enumerate(read_text(path).splitlines(), 1):
            s = strip_comment(raw)
            if not s:
                continue
            where = "%s:%d" % (fn, ln)
            key, _, val = s.partition(" ")
            key, val = key.lower(), val.strip()
            if key == "quest":
                q = dict(id=val, file=fn, line=ln, steps=[], fields={})
                quests.append(q)
                st = None
            elif q is None:
                ctx.err(where, "%r outside of a quest" % key)
            elif key == "step":
                st = dict(text=val, line=ln, fields={})
                q["steps"].append(st)
            elif key in ("name", "town", "kind", "pipboy", "active", "order",
                         "giver", "unlock", "parent", "lockhint", "repeatable") or \
                    (st is None and key in ("done", "fail")):
                if key in q["fields"]:
                    ctx.err(where, "duplicate %r" % key)
                q["fields"][key] = (val, where)
            elif st is not None and key in ("where", "target", "done", "show", "count",
                                            "note", "src", "alt"):
                if key in st["fields"]:
                    ctx.err(where, "duplicate %r" % key)
                st["fields"][key] = (val, where)
            else:
                ctx.err(where, "unknown keyword %r" % key)
    return quests


def quest_key(qid):
    return zlib.crc32(qid.encode()) & 0x3fffffff


def compile_model(ctx, raw_quests):
    pip = {q["pipboy"]: q for q in ctx.quests_txt}
    loc_town = {1500 + i: t for t, i in TOWNS}
    model = []
    seen_ids = set()
    seen_pip = set()
    for rq in raw_quests:
        f = rq["fields"]
        w0 = "%s:%d" % (rq["file"], rq["line"])
        if rq["id"] in seen_ids or not re.fullmatch(r"[a-z0-9_]+", rq["id"]):
            ctx.err(w0, "bad or duplicate quest id %r" % rq["id"])
        seen_ids.add(rq["id"])
        q = dict(id=rq["id"], key=quest_key(rq["id"]), file=rq["file"], steps=[])
        q["name"] = f.get("name", ("", w0))[0]
        if not q["name"] or len(q["name"]) > MAX_NAME:
            ctx.err(w0, "quest name missing or longer than %d: %r" % (MAX_NAME, q["name"]))
        q["town"] = f.get("town", ("", w0))[0]
        if q["town"] not in TOWN_ORDER:
            ctx.err(w0, "unknown town %r" % q["town"])
        q["kind"] = f.get("kind", ("optional", w0))[0]
        if q["kind"] not in ("main", "optional", "companion"):
            ctx.err(w0, "kind must be main, optional or companion")
        q["order"] = int(f["order"][0]) if "order" in f else 50
        q["pipboy"] = int(f["pipboy"][0]) if "pipboy" in f else 0
        entry = None
        if q["pipboy"]:
            entry = pip.get(q["pipboy"])
            if not entry:
                ctx.err(w0, "pipboy %d is not an active line in quests.txt" % q["pipboy"])
            else:
                seen_pip.add(q["pipboy"])
                q["gvar"] = entry["gvar"]
                ctx.check_gvar(entry["gvar"], w0)
        q["desc"] = ctx.quest_msg.get(q["pipboy"], "") if q["pipboy"] else ""
        # hierarchy: who gives it, what unlocks it, which quest it follows from
        for fld in ("giver", "lockhint"):
            q[fld] = f.get(fld, ("", w0))[0]
            if len(q[fld]) > MAX_STEP_TEXT:
                ctx.err(f[fld][1], "%s longer than %d chars" % (fld, MAX_STEP_TEXT))
        q["unlock"] = ctx.cond(*f["unlock"]) if "unlock" in f else [[C_TRUE, 0, 0, 0, 0]]
        q["parent"] = f["parent"][0] if "parent" in f else ""
        # repeatable jobs are not latched: their steps/done may legitimately go back
        q["repeatable"] = 1 if "repeatable" in f else 0
        q["_parent_where"] = f["parent"][1] if "parent" in f else w0
        for fld in ("active", "done", "fail"):
            if fld in f:
                q[fld] = ctx.cond(f[fld][0], f[fld][1])
            elif entry and fld == "active":
                q[fld] = [[C_GVAR, entry["gvar"], 0, OPS[">="], entry["display"]]]
            elif entry and fld == "done":
                q[fld] = [[C_GVAR, entry["gvar"], 0, OPS[">="], entry["completed"]]]
            elif fld == "fail":
                q[fld] = [[C_FALSE, 0, 0, 0, 0]]
            else:
                ctx.err(w0, "quest without pipboy line needs an explicit %r" % fld)
                q[fld] = [[C_FALSE, 0, 0, 0, 0]]
        if not rq["steps"]:
            ctx.err(w0, "quest has no steps")
        for rs in rq["steps"]:
            sw = "%s:%d" % (rq["file"], rs["line"])
            sf = rs["fields"]
            s = dict(text=rs["text"])
            if not s["text"] or len(s["text"]) > MAX_STEP_TEXT:
                ctx.err(sw, "step text missing or longer than %d chars: %r"
                        % (MAX_STEP_TEXT, s["text"]))
            s["alt"] = 1 if "alt" in sf else 0
            if s["alt"] and not q["steps"]:
                ctx.err(sw, "'alt' on the first step of a quest (it is an alternative to the step before)")
            s["note"] = sf.get("note", ("", sw))[0]
            if len(s["note"]) > MAX_NOTE:
                ctx.err(sw, "note longer than %d chars" % MAX_NOTE)
            s["src"] = sf.get("src", ("", sw))[0]
            # where: list of (map, elev) ; elev -1 = any
            s["where"] = []
            if "where" in sf:
                for item in [x.strip() for x in sf["where"][0].split(",") if x.strip()]:
                    m, _, e = item.partition(":")
                    s["where"].append((ctx.map_num(m, sf["where"][1]), int(e) if e else -1))
            s["where_names"] = [x.strip().split(":")[0].upper()
                                for x in sf.get("where", ("", sw))[0].split(",") if x.strip()]
            for mn in s["where_names"]:
                if mn not in MAP_INFO:
                    ctx.warn(sw, "map %s has no label/town in MAP_INFO" % mn)
            # target
            s["tkind"], s["targets"] = T_NONE, []
            if "target" in sf:
                tv, tw = sf["target"]
                kind, _, rest = tv.partition(" ")
                if kind not in TARGET_KINDS:
                    ctx.err(tw, "unknown target kind %r" % kind)
                else:
                    s["tkind"] = TARGET_KINDS[kind]
                    for tok in [x.strip() for x in rest.split(",") if x.strip()]:
                        if s["tkind"] == T_TILE:
                            tile, _, el = tok.partition(":")
                            tnum = int(tile)
                            if not 0 <= tnum < 40000:
                                ctx.err(tw, "tile %d out of range" % tnum)
                            s["targets"].append(tnum * 4 + (int(el) + 1 if el else 0))
                        elif s["tkind"] == T_NPC:
                            sid = ctx.value(tok, "SCRIPT", tw)
                            if not 1 <= sid <= 1100:
                                ctx.err(tw, "script id %d out of range" % sid)
                            s["targets"].append(sid)
                        else:
                            pid = ctx.value(tok, "PID", tw)
                            ctx.check_pid(pid, tw, s["tkind"])
                            s["targets"].append(pid)
                    if not s["targets"]:
                        ctx.err(tw, "target without values")
                    if not s["where"]:
                        ctx.warn(tw, "target without 'where' (searched on every map)")
            s["count"] = []
            if "count" in sf:
                for tok in [x.strip() for x in sf["count"][0].split(",") if x.strip()]:
                    pid = ctx.value(tok, "PID", sf["count"][1])
                    ctx.check_pid(pid, sf["count"][1], T_CRITTER)
                    s["count"].append(pid)
            if "done" not in sf:
                ctx.err(sw, "step without 'done'")
                s["done"] = [[C_FALSE, 0, 0, 0, 0]]
            else:
                s["done"] = ctx.cond(*sf["done"])
            s["show"] = ctx.cond(*sf["show"]) if "show" in sf else [[C_TRUE, 0, 0, 0, 0]]
            q["steps"].append(s)
        model.append(q)

    # first pass for every Pip-Boy quest without hand-written steps
    for e in ctx.quests_txt:
        if e["pipboy"] in seen_pip:
            continue
        town = loc_town.get(e["location"], "Vault 13")
        desc = ctx.quest_msg.get(e["pipboy"], "Quest %d" % e["pipboy"])
        qid = "auto_%d" % e["pipboy"]
        short = desc.rstrip(".")
        name = short if len(short) <= MAX_NAME else short[:MAX_NAME - 3].rstrip() + "..."
        text = short if len(short) <= MAX_STEP_TEXT else short[:MAX_STEP_TEXT - 3].rstrip() + "..."
        ctx.warn("quests.txt", "pipboy %d (%s) has no hand-written steps; generated" % (
            e["pipboy"], desc))
        ctx.check_gvar(e["gvar"], "quests.txt pipboy %d" % e["pipboy"])
        model.append(dict(
            id=qid, key=quest_key(qid), file="(generated)", name=name, town=town,
            giver="", lockhint="", unlock=[[C_TRUE, 0, 0, 0, 0]], parent="", _parent_where="", repeatable=0,
            kind="main" if e["pipboy"] in (100, 103, 104) else "optional",
            order=90, pipboy=e["pipboy"], gvar=e["gvar"], desc=desc,
            active=[[C_GVAR, e["gvar"], 0, OPS[">="], e["display"]]],
            done=[[C_GVAR, e["gvar"], 0, OPS[">="], e["completed"]]],
            fail=[[C_FALSE, 0, 0, 0, 0]],
            steps=[dict(text=text, note=desc[:MAX_NOTE], src="quests.txt", where=[],
                        where_names=[], tkind=T_NONE, targets=[], count=[],
                        done=[[C_GVAR, e["gvar"], 0, OPS[">="], e["completed"]]],
                        show=[[C_TRUE, 0, 0, 0, 0]], alt=0)]))

    # sort: main first, then by town order, then order
    def sk(q):
        return (0 if q["kind"] == "main" else 1, q["order"] if q["kind"] == "main" else 0,
                TOWN_ORDER.index(q["town"]) if q["town"] in TOWN_ORDER else 99, q["order"])
    model.sort(key=sk)
    ids = {q["id"]: q for q in model}
    for q in model:
        if q["parent"] and q["parent"] not in ids:
            ctx.err(q["_parent_where"], "unknown parent quest %r" % q["parent"])
            q["parent"] = ""
    for q in model:
        seen, p = {q["id"]}, q["parent"]
        while p:
            if p in seen:
                ctx.err(q["_parent_where"], "parent cycle through %r" % p)
                q["parent"] = ""
                break
            seen.add(p)
            p = ids[p]["parent"]
    keys = [q["key"] for q in model]
    if len(set(keys)) != len(keys):
        ctx.err("model", "quest key hash collision")
    return model


def build(files=None):
    ctx = Ctx()
    raw = parse_step_files(ctx, files)
    model = compile_model(ctx, raw)
    return ctx, model


if __name__ == "__main__":
    ctx, model = build()
    for w in ctx.warnings:
        print("warning:", w)
    for e in ctx.errors:
        print("ERROR:", e)
    print("%d quests, %d steps, %d errors" % (
        len(model), sum(len(q["steps"]) for q in model), len(ctx.errors)))
    sys.exit(1 if ctx.errors else 0)

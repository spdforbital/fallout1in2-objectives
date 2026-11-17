#!/usr/bin/env python3
"""Offline checks for the Objectives data.

1. Validation (objdata): every GVAR / PID / SCRIPT / MAP name exists, GVARs are real
   (in range of Vault13.gam and not RESERVED slots), text lengths, syntax.
2. Round trip: parse build/objectives_data.h back and compare with the flat model.
3. Pool integrity: condition / list offsets in range, OR atoms never first/last.
4. Simulation: evaluate quests the way gl_objectives.ssl does on a few GVAR states
   (new game, chip returned, ...) and check the expected quests show up.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import objdata as od  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)


def parse_header(path):
    """Read back the generated SSL: returns {array: {index: value}}, sizes, defines."""
    arrays, sizes, defines = {}, {}, {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        m = re.match(r"#define (\w+) \((-?\d+)\)", line)
        if m:
            defines[m.group(1)] = int(m.group(2))
            continue
        m = re.match(r"(\w+) := create_array\((\d+), 0\);", line)
        if m:
            sizes[m.group(1)] = int(m.group(2))
            arrays[m.group(1)] = {}
            continue
        m = re.match(r'(\w+)\[(\d+)\] := (".*"|-?\d+);', line)
        if m:
            v = m.group(3)
            arrays[m.group(1)][int(m.group(2))] = v[1:-1] if v.startswith('"') else int(v)
    return arrays, sizes, defines


def roundtrip(flat):
    arrays, sizes, defines = parse_header(os.path.join(od.ROOT, "build", "objectives_data.h"))
    check(defines.get("OBJ_NQ") == len(flat["quests"]), "OBJ_NQ mismatch")
    check(defines.get("OBJ_NS") == len(flat["steps"]), "OBJ_NS mismatch")

    def get(name, i, default):
        return arrays[name].get(i, default)

    for i, q in enumerate(flat["quests"]):
        for fld, arr in (("key", "q_key"), ("town", "q_town"), ("main", "q_main"),
                         ("active", "q_active"), ("done", "q_done"), ("fail", "q_fail"),
                         ("s0", "q_s0"), ("sn", "q_sn")):
            check(get(arr, i, 0) == q[fld], "roundtrip %s[%d]" % (arr, i))
        check(get("q_name", i, "") == q["name"].replace('"', "'"), "roundtrip q_name[%d]" % i)
    for i, s in enumerate(flat["steps"]):
        for fld in ("w0", "wn", "tkind", "t0", "tn", "k0", "kn", "done", "show"):
            check(get("s_" + fld, i, 0) == s[fld], "roundtrip s_%s[%d]" % (fld, i))
        check(get("s_text", i, "") == s["text"].replace('"', "'"), "roundtrip s_text[%d]" % i)
    for name, pool in (("c_pool", flat["cpool"]), ("i_pool", flat["ipool"])):
        check(sizes[name] >= len(pool), name + " size")
        for i, v in enumerate(pool):
            check(get(name, i, 0) == v, "roundtrip %s[%d]" % (name, i))
    return arrays


def pools(flat):
    cp, ip = flat["cpool"], flat["ipool"]
    offs = set()
    for q in flat["quests"]:
        offs |= {q["active"], q["done"], q["fail"]}
        check(0 <= q["s0"] and q["s0"] + q["sn"] <= len(flat["steps"]), "quest step range")
    for s in flat["steps"]:
        offs |= {s["done"], s["show"]}
        for o, n in ((s["w0"], s["wn"]), (s["t0"], s["tn"]), (s["k0"], s["kn"])):
            check(o + n <= len(ip), "ipool range")
    for o in offs:
        n = cp[o]
        check(n >= 1 and o + 1 + 5 * n <= len(cp), "cpool range at %d" % o)
        types = [cp[o + 1 + 5 * i] for i in range(n)]
        check(types[0] != od.C_OR and types[-1] != od.C_OR, "OR at edge of condition %d" % o)
        check(all(1 <= cp[o + 1 + 5 * i + 3] <= 6 for i in range(n)
                  if types[i] in (od.C_GVAR, od.C_ITEM, od.C_MVAR)), "bad op in %d" % o)


# --- simulation (mirrors EvalCond / ComputeStatus in gl_objectives.ssl) -----------------
def cmp(v, op, c):
    return {1: v == c, 2: v != c, 3: v >= c, 4: v <= c, 5: v > c, 6: v < c}[op]


def evalc(cp, off, st):
    n, grp = cp[off], True
    for i in range(n):
        t, a, b, op, c = cp[off + 1 + 5 * i: off + 6 + 5 * i]
        if t == od.C_OR:
            if grp:
                return True
            grp = True
        elif grp:
            if t == od.C_GVAR:
                grp = cmp(st["g"].get(a, 0), op, c)
            elif t == od.C_ITEM:
                grp = cmp(st["items"].get(a, 0), op, c)
            elif t == od.C_MAP:
                grp = st["map"] == a
            elif t == od.C_PARTY:
                grp = cmp(1 if a in st.get("party", ()) else 0, op, c)
            elif t == od.C_TOWN:
                grp = cmp(st.get("town", {}).get(a, 0), op, c)
            elif t == od.C_MVAR:
                grp = cmp(st["mvar"].get(a * 1000 + b, 0), op, c)
            else:
                grp = t == od.C_TRUE
    return grp


def status(flat, st):
    cp, out = flat["cpool"], {}
    for q in flat["quests"]:
        if evalc(cp, q["active"], st) and evalc(cp, q["fail"], st):
            s = "failed"
        elif evalc(cp, q["done"], st):
            s = "done"
        elif evalc(cp, q["active"], st):
            s = "active"
        else:
            s = "inactive"
        if s == "inactive" and not evalc(cp, q["unlock"], st):
            s = "locked"
        cur = None
        if s == "active":
            def group_done(k):
                g = k
                while flat["steps"][g].get("alt"):
                    g -= 1
                j = g
                while j < q["s0"] + q["sn"] and (j == g or flat["steps"][j].get("alt")):
                    sj = flat["steps"][j]
                    if evalc(cp, sj["show"], st) and evalc(cp, sj["done"], st):
                        return True
                    j += 1
                return False
            for k in range(q["s0"], q["s0"] + q["sn"]):
                stp = flat["steps"][k]
                if evalc(cp, stp["show"], st) and not group_done(k):
                    cur = stp["text"]
                    break
        out[q["id"]] = (s, cur)
    return out


def initial_gvars():
    vals = {}
    i = 0
    for line in od.read_text(os.path.join(od.BASE, "data", "Vault13.gam")).splitlines():
        m = re.match(r"\s*\w+\s*:=\s*(-?\d+)\s*;", line)
        if m:
            vals[i] = int(m.group(1))
            i += 1
    return vals


def simulate(flat, const):
    G = const["GVAR"]
    base = dict(g=initial_gvars(), items={}, map=const["MAP"]["MAP_V13ENT"], mvar={})
    s0 = status(flat, base)
    active0 = sorted(k for k, v in s0.items() if v[0] == "active")
    print("new game, active quests:", active0)
    print("   waterchip next step:", s0["waterchip"][1])
    check(s0["waterchip"][0] == "active", "waterchip must be active at game start")
    check(s0["waterchip"][1] is not None, "waterchip must have a current step at game start")
    check(s0["master"][0] in ("inactive", "locked") and s0["vats"][0] in ("inactive", "locked"),
          "master/vats must not be active at game start")
    # chip in inventory -> next step is bringing it back
    st = json.loads(json.dumps(base), object_hook=lambda d: {
        (int(k) if k.lstrip("-").isdigit() else k): v for k, v in d.items()})
    st["items"][const["PID"]["PID_WATER_CHIP"]] = 1
    s1 = status(flat, st)
    print("carrying the chip:", s1["waterchip"][1])
    check(s1["waterchip"][1] and "Overseer" in s1["waterchip"][1], "chip carried -> Overseer step")
    # chip returned, Overseer gave the next quests
    st["g"][G["GVAR_VAULT_WATER"]] = 2
    st["g"][G["GVAR_QUEST_VAULT13_2_MASTER"]] = 1
    st["g"][G["GVAR_QUEST_VAULT13_3_KILL_VATS"]] = 1
    st["items"] = {}
    s2 = status(flat, st)
    print("chip returned:", {k: s2[k] for k in ("waterchip", "master", "vats")})
    check(s2["waterchip"][0] == "done", "waterchip done after return")
    check(s2["master"][0] == "active" and s2["vats"][0] == "active", "master+vats active")
    # GVAR-based steps must not start out ticked: a step whose done-condition already
    # holds on a new game (with no items, unknown map) is almost always a wrong GVAR
    st0 = dict(base, map=-5)
    for q in flat["quests"]:
        for k in range(q["s0"], q["s0"] + q["sn"]):
            stp = flat["steps"][k]
            if evalc(flat["cpool"], stp["show"], st0) and evalc(flat["cpool"], stp["done"], st0):
                check(False, "step already done on a new game: %s / %s" % (q["id"], stp["text"]))
    # every step can be reached: its done-condition is not constant false
    for i, s in enumerate(flat["steps"]):
        cp = flat["cpool"]
        n = cp[s["done"]]
        types = {cp[s["done"] + 1 + 5 * k] for k in range(n)}
        if types == {od.C_FALSE}:
            print("note: step %d (%s) can never be ticked off" % (i, s["text"]))


def main():
    ctx, model = od.build()
    for e in ctx.errors:
        FAILS.append("validation: " + e)
    import build_data
    flat = build_data.flatten(model, ctx)
    if os.path.exists(os.path.join(od.ROOT, "build", "objectives_data.h")):
        roundtrip(flat)
    else:
        FAILS.append("build/objectives_data.h missing - run build_data.py")
    pools(flat)
    simulate(flat, ctx.const)
    used = {k: len(v) for k, v in ctx.used.items()}
    print("names checked against headers:", used)
    print("%d quests (%d hand-written, %d generated), %d steps" % (
        len(model), sum(1 for q in model if q["file"] != "(generated)"),
        sum(1 for q in model if q["file"] == "(generated)"), len(flat["steps"])))
    if FAILS:
        print("\n".join("FAIL: " + f for f in FAILS[:50]))
        print("%d failures" % len(FAILS))
        return 1
    print("all data tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

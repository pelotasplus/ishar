#!/usr/bin/env python3
"""
T29c: which VM primitives does one game action use?

A plain before/after diff is useless here: the interpreter runs flat out even when the
party is standing still, so 264 functions move during an idle window. This measures an
idle window and an equal-length action window and reports the EXCESS -- handlers that ran
far more during the action than during idle, and handlers that ran only during it.

    tools/t29c-action.py <label> <seconds> <shell command performing the action>
"""
import importlib.util, json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
sp = importlib.util.spec_from_file_location("vmi", os.path.join(HERE, "tools", "vmi.py"))
vmi = importlib.util.module_from_spec(sp); sp.loader.exec_module(vmi)
BY_ADDR = {}
for opc, a in vmi.STMT.items():
    BY_ADDR.setdefault(a, []).append(opc)

def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=120).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})

def snap():
    d = mcp("list_functions", {"limit": 5000})
    fs = d["Functions"] if isinstance(d, dict) and "Functions" in d else d
    # Key on (segment, offset). Functions live in five segments and two offsets occur in
    # more than one, so keying on the offset alone merged them -- which mislabelled
    # seg_0e97:038b, the sprite blitter, as seg_0000:038b in every earlier diff (T40b).
    return {(f.get("Address", {}).get("Segment", -1),
             f.get("Address", {}).get("Offset", -1)): f.get("CalledCount", 0) for f in fs}

label, secs, cmd = sys.argv[1], float(sys.argv[2]), " ".join(sys.argv[3:])
a = snap(); time.sleep(secs); b = snap()          # idle window
subprocess.run(cmd, shell=True, capture_output=True)
time.sleep(secs); c = snap()                      # action window
idle = {k: b.get(k, 0) - a.get(k, 0) for k in b}
act  = {k: c.get(k, 0) - b.get(k, 0) for k in c}
rows = []
for k, v in act.items():
    i = idle.get(k, 0)
    if v <= 0:
        continue
    if i == 0:
        rows.append((float("inf"), v, i, k))       # ran only during the action
    elif v > i * 3 and v - i > 200:
        rows.append((v / i, v, i, k))
rows.sort(key=lambda r: (-r[0], -r[1]))
print(f"[{label}] handlers used far more by the action than by idling:")
SEGNAME = {0x17d:"seg_0000", 0xabe:"seg_0abe", 0x1014:"seg_0e97", 0x1554:"seg_13d7", 0xf000:"bios"}
for ratio, v, i, key in rows[:20]:
    seg, off = key
    opcs = BY_ADDR.get(off, []) if seg == 0x17d else []
    nm = vmi.NAME.get(off, "") if seg == 0x17d else ""
    tag = ("  opcode " + ", ".join(f"{o:#04x}" for o in opcs)) if opcs else ""
    r = "only" if ratio == float("inf") else f"{ratio:5.1f}x"
    sn = SEGNAME.get(seg, f"seg_{seg:04x}")
    print(f"   {r:>6}  action {v:<9d} idle {i:<9d} {sn}:{off:04x} {nm[:24]:24s}{tag}")
json.dump([(list(r[3]), r[1], r[2]) for r in rows],
          open(os.path.join(HERE, ".ish", f"t29c-{label}.json"), "w"))

#!/usr/bin/env python3
"""
T29c: attribute VM primitives to game actions by diffing call counts.

Spice86 counts calls per function, and every statement handler is a function reached
through `call cs:[bx+24h]`. Snapshot, perform one action, snapshot again: the handlers
whose counts moved are the primitives that action used. Addresses are mapped back to
opcode numbers through the statement table, so the answer is "opcode 0x4b", not a bare
address.

    tools/t29c-attribute.py snap                 # take a baseline
    tools/t29c-attribute.py diff <label>         # diff against the baseline and label it
"""
import importlib.util, json, os, sys, urllib.request

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
    out = {}
    for f in fs:
        # The field is CalledCount, and Address is {Offset, Segment, Linear}. Segment is
        # the load segment (0x17d), so Offset is a seg_0000 offset directly.
        a = f.get("Address", {})
        off = a.get("Offset", -1) if isinstance(a, dict) else -1
        out[off] = f.get("CalledCount", 0)
    return out

PATH = os.path.join(HERE, ".ish", "t29c-base.json")
if sys.argv[1] == "snap":
    json.dump(snap(), open(PATH, "w"))
    print(f"baseline: {len(json.load(open(PATH)))} functions")
else:
    label = sys.argv[2] if len(sys.argv) > 2 else "action"
    base = json.load(open(PATH))
    now = snap()
    moved = []
    for k, v in now.items():
        d = v - base.get(k, 0)
        if d > 0:
            moved.append((d, k))
    moved.sort(reverse=True)
    print(f"[{label}] {len(moved)} functions moved")
    for d, off in moved[:25]:
        opcs = BY_ADDR.get(off, [])
        nm = vmi.NAME.get(off, "")
        tag = ("  <- statement opcode " + ", ".join(f"{o:#04x}" for o in opcs)) if opcs else ""
        print(f"   +{d:<8d} seg_0000:{off:04x}  {nm[:34]:34s}{tag}")
    json.dump(moved, open(os.path.join(HERE, ".ish", f"t29c-{label}.json"), "w"))

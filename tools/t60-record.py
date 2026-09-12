#!/usr/bin/env python3
"""Snapshot the VM global area to a named file, and diff two snapshots.

`tools/t59-globals.py` drives the game itself, which is wrong for anything that needs
hand-driving in between -- recruiting an NPC takes a menu click, a verb click and a target
click, and the party has to be standing in the right place first. This takes the snapshot
and nothing else, so the steps between two of them can be anything.

    tools/t60-record.py snap before
    tools/t60-record.py diff before after

`T60_SIZE` sets how much of the area to take; the default 64 KB is one whole segment, which
is as much as a near pointer into it can address.
"""
import json, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import urllib.request

st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
SIZE = int(os.environ.get('T60_SIZE', '0x10000'), 0)

def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})

def path(name):
    return os.path.join(HERE, ".ish", f"t60-{name}.bin")

def do_snap(name):
    cpu = mcp("read_cpu_state")
    g = Rsp(st["gdb"])
    p = g.read_mem(cpu["SS"] * 16 + 0x0bf6, 4)
    base = ((p[3] << 8 | p[2]) * 16) + (p[1] << 8 | p[0])
    b = bytearray()
    while len(b) < SIZE:
        b += g.read_mem(base + len(b), min(4096, SIZE - len(b)))
    g.cont()
    open(path(name), "wb").write(b)
    print(f"{name}: {SIZE} bytes from {base:#07x}  party ({b[0x137c]},{b[0x137d]}) "
          f"region {b[0x3eac]}  step {b[0x438b]}/{b[0x438c]}")

def do_diff(a, b, gap=4):
    x, y = open(path(a), "rb").read(), open(path(b), "rb").read()
    diff = [o for o in range(SIZE) if x[o] != y[o]]
    spans = []
    for o in diff:
        if spans and o - spans[-1][1] <= gap:
            spans[-1][1] = o
        else:
            spans.append([o, o])
    print(f"{len(diff)} bytes differ in {len(spans)} spans")
    for s, e in spans:
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in y[s:e+1][:16])
        print(f"  +{s:04x}..{e:04x}  {x[s:e+1][:16].hex()} -> {y[s:e+1][:16].hex()}  |{txt}|")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "snap":
        do_snap(sys.argv[2])
    elif sys.argv[1] == "diff":
        do_diff(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)

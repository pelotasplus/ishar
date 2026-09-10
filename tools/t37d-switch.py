#!/usr/bin/env python3
"""
T37c/d: catch script SWITCHES instead of statements.

A breakpoint on vm_run stops once per statement -- its loop jumps back to its own
entry -- and that stalls the game so badly it stops advancing at all (T37c: the screen
did not move in 270s). But `mov es:[bp-8], si` at seg_0000:26b2 runs only when vm_run
RETURNS, i.e. once per script yield, so a MEMORY_WRITE there is far cheaper and is
what actually marks a script starting or resuming.

The slot is at a fixed linear address while the frame is stable; pass it in.
"""
import json, os, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
_ns = {}
exec(open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0], _ns)
decode = _ns["decode"]
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:]); return j.get("result", {}).get("structuredContent", j)

slot = int(sys.argv[1], 16)
secs = int(sys.argv[2]) if len(sys.argv) > 2 else 90
assets = {}
for n in sorted(os.listdir(GAME)):
    if n.lower().endswith(".io"):
        try: assets[n] = decode(open(os.path.join(GAME, n), "rb").read())[0]
        except Exception: pass
g = Rsp(st["gdb"]); mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": slot, "type": "MEMORY_WRITE", "condition": None})
g.cont()
print(f"MEMORY_WRITE at {slot:#x} (the script PC slot); {secs}s")
first, stops, t0 = {}, 0, time.time()
while time.time() - t0 < secs:
    g.cont()
    if g.wait_stop(timeout=max(1, secs - (time.time() - t0))) is None:
        continue
    stops += 1
    r = g.registers()
    lin = r["ds"] * 16 + (r["si"] & 0xffff)
    run = bytes(g.read_mem(lin, 64))
    cands = [(n, d.find(run)) for n, d in assets.items()
             if d.find(run) >= 0 and d.find(run, d.find(run) + 1) < 0]
    if len(cands) == 1:
        n, i = cands[0]
        if n not in first:
            first[n] = i
            print(f"  {time.time()-t0:6.1f}s  NEW SCRIPT {n} at offset {i}")
mcp("clear_breakpoints"); g.cont()
print(f"\n{stops} stops, {len(first)} assets: {json.dumps(first)}")
json.dump(first, open(os.path.join(HERE, ".ish", "t37d.json"), "w"), indent=1)

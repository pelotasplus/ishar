#!/usr/bin/env python3
"""
Who writes the viewport? MEMORY_WRITE breakpoint, no keys sent during the probe.

T11p's original list (0x5534, 0x817b, ... 0xab76) was wrong twice over: every
address was 0x17d0 too high (the IP-is-linear bug), and the corrected addresses
land on wait_loop and the VM's hottest helpers -- i.e. they were phantom stops
from key-sends pausing the machine, not writers. So: send nothing, and report the
raw stop packet alongside the IP so a real breakpoint hit is distinguishable.
"""
import json, os, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:]); return j.get("result", {}).get("structuredContent", j)

args=[a for i,a in enumerate(sys.argv[1:]) if not a.startswith("--") and not (i>0 and sys.argv[i] in ("--base","--width"))]
x, y = int(args[0]), int(args[1])
secs = int(args[2]) if len(args) > 2 else 25
# --base <hex linear> targets an arbitrary buffer; the sprite path's destination
# comes from the far pointer at ss:[0bc8] and moves, so it must be read each run.
if "--base" in sys.argv:
    base = int(sys.argv[sys.argv.index("--base") + 1], 16)
elif "--back" in sys.argv:
    base = 0xE0000
else:
    base = 0xA0000
width = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 320
addr = base + y * width + x
load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": addr, "type": "MEMORY_WRITE", "condition": None})
print(f"MEMORY_WRITE at {addr:#x} = {"backbuffer" if base==0xE0000 else "vram"} ({x},{y}); load={load:#x}; sending no keys")
sites, pkts, t0 = {}, {}, time.time()
while time.time() - t0 < secs:
    g.cont()
    p = g.wait_stop(timeout=max(1, secs - (time.time() - t0)))
    if p is None:
        continue
    r = g.registers()
    off = r["ip"] - load * 16          # ip is LINEAR
    sites[f"{off:#07x}"] = sites.get(f"{off:#07x}", 0) + 1
    pkts[str(p)[:40]] = pkts.get(str(p)[:40], 0) + 1
mcp("clear_breakpoints"); g.cont()
print(f"{sum(sites.values())} stops from {len(sites)} sites")
for k, v in sorted(sites.items(), key=lambda kv: -kv[1])[:10]:
    print(f"   image {k}  x{v}")
print("stop packets seen:", pkts)

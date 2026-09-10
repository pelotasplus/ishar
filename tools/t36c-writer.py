#!/usr/bin/env python3
"""Who writes the portrait's pixels? Break on a VRAM write inside buste's sprite."""
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

x, y = int(sys.argv[1]), int(sys.argv[2])
secs = int(sys.argv[3]) if len(sys.argv) > 3 else 20
addr = 0xA0000 + y * 320 + x
load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": addr, "type": "MEMORY_WRITE", "condition": None})
print(f"break on write to {addr:#x} (screen {x},{y}); load={load:#x}")
seen, t0 = {}, time.time()
while time.time() - t0 < secs:
    g.cont()
    if g.wait_stop(timeout=max(1, secs - (time.time() - t0))) is None:
        continue
    r = g.registers()
    ip, cs = r["ip"], r["cs"]
    # ip is LINEAR (CLAUDE.md); express it as an image offset
    off = ip - load * 16
    key = f"{off:#07x}"
    seen[key] = seen.get(key, 0) + 1
mcp("clear_breakpoints"); g.cont()
print(f"{sum(seen.values())} writes from {len(seen)} sites")
for k, v in sorted(seen.items(), key=lambda kv: -kv[1])[:12]:
    print(f"   image {k}  x{v}")

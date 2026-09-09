#!/usr/bin/env python3
"""
T29d: does Ishar probe INT 33h at startup?

The game never calls INT 33h once it is running, but that is consistent with two very
different stories: it has no mouse support at all, or it probed once during startup,
was told there is no mouse, and disabled the pointer. Only a trace from boot can tell
them apart, and the answer decides whether the ACTION menu is reachable at all.
"""
import json, os, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 90
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:]); return j.get("result", {}).get("structuredContent", j)
g = Rsp(st["gdb"])
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": 0xF00DD, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
print(f"INT 33h breakpoint armed from boot; {BUDGET}s", flush=True)
hits = 0; t0 = time.time()
while time.time() - t0 < BUDGET and hits < 20:
    g.cont()
    if g.wait_stop(timeout=max(1, BUDGET - (time.time() - t0))) is None: break
    r = g.registers()
    if (r["cs"] & 0xffff) != 0xf000 or (r["ip"] & 0xffff) != 0xdd: continue
    hits += 1
    ret = int.from_bytes(g.read_mem(r["ss"]*16 + (r["sp"] & 0xffff), 2), "little")
    print(f"  AX={r['ax']&0xffff:#06x} BX={r['bx']&0xffff:#06x} "
          f"CX={r['cx']&0xffff:#06x} DX={r['dx']&0xffff:#06x}  from {ret:#06x}  "
          f"t={time.time()-t0:.1f}s", flush=True)
mcp("clear_breakpoints")
print(f"{hits} INT 33h calls during startup")
g.cont()

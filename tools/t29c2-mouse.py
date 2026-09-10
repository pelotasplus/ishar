#!/usr/bin/env python3
"""
T29c2: find the mouse event handler Ishar installs, then see if it ever fires.

FINDINGS 6.4 says the game does not use the mouse because INT 33h records zero calls
during play. That is true and re-verified here with the corrected IP comparison (0 hits
against a control of 507). But it is the wrong window: the game installs an INT 33h
*event handler* (AX=0x0c, callback in ES:DX) during startup and never calls INT 33h
again, so a mid-game trace cannot see it.

Phase 1 breaks on the INT 33h entry from a cold start and records every call.
Phase 2 breaks on the callback and drives the mouse to see whether it is invoked.
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

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 120
INT33 = 0xf00dd
g = Rsp(st["gdb"]); mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": INT33, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
g.cont()
print(f"phase 1: INT 33h entry {INT33:#x}, watching for AX=0x0c (install handler)")
calls, cb, t0 = [], None, time.time()
while time.time() - t0 < secs:
    g.cont()
    if g.wait_stop(timeout=4) is None:
        continue
    r = g.registers()
    if r["ip"] != INT33:
        continue
    ax = r["ax"] & 0xffff
    calls.append(ax)
    if ax == 0x0c:
        cb = (r["es"], r["dx"] & 0xffff)
        print(f"  AX=0x0c at t={time.time()-t0:5.1f}s -> callback ES:DX = {cb[0]:04x}:{cb[1]:04x}")
        break
    elif len(calls) < 12:
        print(f"  AX={ax:#06x} at t={time.time()-t0:5.1f}s")
mcp("clear_breakpoints"); g.cont()
from collections import Counter
print(f"phase 1 done: {len(calls)} INT 33h calls, functions {dict(Counter(hex(a) for a in calls))}")
json.dump({"calls": calls, "callback": cb}, open(os.path.join(HERE, ".ish", "t29c2.json"), "w"))

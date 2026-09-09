#!/usr/bin/env python3
"""
Minimal breakpoint probe: arm one execution breakpoint, count hits, print.

Deliberately does nothing else, so a zero result means the harness is not
delivering stops rather than something in a bigger script being wrong (T27b).

    tools/bphits.py 0x93a6 [seconds]
"""
import json, os, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
OFF = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x93a6
SECS = int(sys.argv[2]) if len(sys.argv) > 2 else 15
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:]); return j.get("result", {}).get("structuredContent", j)
load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
entry = load * 16 + OFF
mcp("clear_breakpoints")
print("breakpoint:", mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None}))
hits = other = 0
where = {}
t0 = time.time()
while time.time() - t0 < SECS and hits < 5:
    g.cont()
    if g.wait_stop(timeout=max(1, SECS - (time.time() - t0))) is None:
        break
    r = g.registers()
    # The stub reports IP as a LINEAR address, not a segment offset, so compare
    # against the linear breakpoint address (T27b).
    if r["ip"] == entry: hits += 1
    else:
        other += 1
        where[(r["cs"] & 0xffff, r["ip"] & 0xffff)] = where.get((r["cs"] & 0xffff, r["ip"] & 0xffff), 0) + 1
mcp("clear_breakpoints"); g.cont()
print(f"seg_0000:{OFF:04x} -> {hits} hits, {other} other stops, in {SECS}s")
for (cs, ip), n in sorted(where.items(), key=lambda kv: -kv[1])[:8]:
    print(f"   other stop at {cs:04x}:{ip:04x}  x{n}")

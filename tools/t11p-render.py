#!/usr/bin/env python3
"""
T11p: find the routine that draws the game viewport.

seg_0e97:038b draws the launcher, title and intro and fires zero times in the
viewport, so the 3D view uses something else. Rather than guess, break on a write
to a pixel in the middle of the viewport and read who wrote it.

If the game renders offscreen and blits, this catches the blit -- which is still
progress, because its source pointer names the offscreen buffer and the next
breakpoint goes there.
"""
import json, os, sys, time, urllib.request, collections

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 40
ADDR = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0xA0000 + 100 * 320 + 160
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))


def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})


load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": ADDR, "type": "MEMORY_WRITE", "condition": None})
print(f"write breakpoint on {ADDR:#x} (load {load:#x}); {BUDGET}s", flush=True)

seen = collections.Counter()
t0 = time.time()
while time.time() - t0 < BUDGET:
    g.cont()
    if g.wait_stop(timeout=max(1, BUDGET - (time.time() - t0))) is None:
        break
    r = g.registers()
    cs, ip = r["cs"] & 0xffff, r["ip"] & 0xffff
    lin = cs * 16 + ip
    rel = lin - load * 16
    ret = int.from_bytes(g.read_mem(r["ss"] * 16 + (r["sp"] & 0xffff), 2), "little")
    seen[(cs, ip, rel, ret)] += 1

mcp("clear_breakpoints")
print(f"\n{sum(seen.values())} writes from {len(seen)} sites:")
for (cs, ip, rel, ret), n in seen.most_common(14):
    print(f"  {cs:04x}:{ip:04x}  image+{rel:#07x}  caller-ret {ret:#06x}  x{n}")
g.cont()

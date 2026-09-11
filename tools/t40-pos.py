#!/usr/bin/env python3
"""
T40: where does a sprite's screen position come from?

Every coordinate in FINDINGS 4.15 was measured off a framebuffer. This catches the
mode-0x10 blit path (seg_0e97:0b4c, the one that draws the portraits and the UI chrome)
and records the destination pointer alongside the sprite's own header, so a position can
be tied back to whatever supplied it.
"""
import json, os, struct, sys, time, urllib.request
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
            return json.loads(ln[5:])["result"].get("structuredContent", {})

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 25
want = int(sys.argv[2]) if len(sys.argv) > 2 else 14
load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
# Address given as a seg_0000 offset. seg_0e97's sprite family is the launcher/intro
# renderer and gets 0 hits in game (control: 44 at vm_run in the same session), so the
# in-game path has to be one of the routines the T29c action diffs named.
entry = load * 16 + int(sys.argv[3], 16) if len(sys.argv) > 3 else load * 16 + 0x038b
g = Rsp(st["gdb"]); mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
g.cont()
print(f"break at {entry:#x} = seg_0e97:0b4c (mode 0x10 sprite path)")
print(f"{'ES:DI dest':>14} {'linear':>8} {'x,y if 320-wide':>16}   sprite header (DS:SI)")
seen, t0 = 0, time.time()
while time.time() - t0 < secs and seen < want:
    g.cont()
    if g.wait_stop(timeout=max(1, secs - (time.time() - t0))) is None:
        continue
    r = g.registers()
    if r["ip"] != entry:
        continue
    seen += 1
    es, di, ds, si = r["es"], r["di"] & 0xffff, r["ds"], r["si"] & 0xffff
    lin = es * 16 + di
    hdr = g.read_mem(ds * 16 + si, 8)
    w0, w1, w2, w3 = struct.unpack("<4H", bytes(hdr))
    # the back buffer is e000 and 320 wide (FORMATS 3.13d / blit_to_screen)
    off = lin - 0xE0000
    xy = f"{off % 320},{off // 320}" if 0 <= off < 64000 else "-"
    print(f"  {es:04x}:{di:04x} {lin:8x} {xy:>16}   mode {w0 & 0xff:#04x} "
          f"{w1+1}x{w2+1} word3={w3:#06x}")
mcp("clear_breakpoints"); g.cont()

#!/usr/bin/env python3
"""T40b: catch the in-game sprite blitter and record where it draws."""
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
addr = int(sys.argv[1], 16); secs = int(sys.argv[2]); want = int(sys.argv[3])
g = Rsp(st["gdb"]); mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": addr, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
g.cont()
print(f"break {addr:#x}; DS:SI = sprite, and the destination the blit uses")
seen, t0 = 0, time.time()
while time.time() - t0 < secs and seen < want:
    g.cont()
    if g.wait_stop(timeout=max(1, secs - (time.time() - t0))) is None: continue
    r = g.registers()
    if r["ip"] != addr: continue
    seen += 1
    ds, si, es, di, ss = r["ds"], r["si"] & 0xffff, r["es"], r["di"] & 0xffff, r["ss"]
    hdr = bytes(g.read_mem(ds*16+si, 8))
    w0, w1, w2, w3 = struct.unpack("<4H", hdr)
    # the sprite path's destination far pointer (FORMATS: ss:[0bc8]/[0bca])
    boff = int.from_bytes(g.read_mem(ss*16+0x0bc8, 2), "little")
    bseg = int.from_bytes(g.read_mem(ss*16+0x0bca, 2), "little")
    blin = bseg*16 + boff
    off = blin - 0xE0000
    xy = f"{off%320},{off//320}" if 0 <= off < 64000 else "-"
    print(f"  mode {w0&0xff:#04x} {w1+1:3d}x{w2+1:<3d} w3={w3:#06x} | "
          f"ES:DI={es:04x}:{di:04x} | buf={bseg:04x}:{boff:04x} -> {xy}")
mcp("clear_breakpoints"); g.cont()

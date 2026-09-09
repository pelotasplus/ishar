#!/usr/bin/env python3
"""T11p: does seg_0e97:02dd draw the viewport, and what does it do with size?"""
import json, os, struct, sys, time, urllib.request, collections
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 30
OFF = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x02dd
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})
load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
entry = load*16 + 0xe970 + OFF
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
print(f"seg_0e97:{OFF:04x} at {entry:#x}; {BUDGET}s", flush=True)
hits = 0; rows = []
t0 = time.time()
while time.time() - t0 < BUDGET and hits < 14:
    g.cont()
    if g.wait_stop(timeout=max(1, BUDGET-(time.time()-t0))) is None: break
    r = g.registers()
    if r["ip"] != entry: continue
    hits += 1
    ss, ds, si = r["ss"], r["ds"], r["si"] & 0xffff
    def w2(o): return int.from_bytes(g.read_mem(ss*16+o, 2), "little")
    try: w0, w1, h1, w3 = struct.unpack("<4H", g.read_mem(ds*16+si, 8))
    except Exception: continue
    clip = (w2(0x0c2c), w2(0x0c2e), w2(0x0c30), w2(0x0c32))
    rows.append((w1+1, h1+1, w0, w3, clip, r["cx"] & 0xffff, r["dx"] & 0xffff, r["bp"] & 0xffff))
mcp("clear_breakpoints")
print(f"\n{hits} hits while walking")
print(f"{'sprite':>10} {'word0':>7} {'word3':>6}  clip rect            CX     DX     BP")
for w,h,w0,w3,clip,cx,dx,bp in rows:
    cw, ch = clip[2]-clip[0]+1, clip[3]-clip[1]+1
    print(f"  {w:3d}x{h:<4d} {w0:#07x} {w3:6d}  ({clip[0]:3d},{clip[1]:3d})-({clip[2]:3d},{clip[3]:3d}) {cw:3d}x{ch:<3d} {cx:5d} {dx:6d} {bp:6d}")
g.cont()

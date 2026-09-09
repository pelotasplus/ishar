#!/usr/bin/env python3
"""
T11m: find how a 4bpp sprite's 0..15 index becomes a 256-colour VGA index.

Sprites carry nibbles; the screen carries bytes. Rather than guess the mapping,
watch one sprite get drawn and read the result: record the sprite and its
destination at one blitter stop, then read the framebuffer back at the *next*
stop, by which time the draw has finished. Every non-transparent pixel gives one
(nibble -> screen byte) pair, and a sprite with a dozen distinct indices pins the
mapping down on its own.

    tools/t11m-palette.py [seconds]
"""
import json, os, struct, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 60
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))


def mcp(t, a=None):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=body, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})


load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
entry = load * 16 + 0xe970 + 0x38b
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
print(f"blitter at {entry:#x}; {BUDGET}s", flush=True)

pending = None
pairs = {}          # nibble -> Counter of screen bytes
t0 = time.time()
while time.time() - t0 < BUDGET:
    g.cont()
    if g.wait_stop(timeout=max(1, BUDGET - (time.time() - t0))) is None:
        break
    r = g.registers()
    if r["ip"] != entry:
        continue

    if pending:                       # the previous sprite is on screen now
        vseg, x0, y0, w, h, px, pitch, cw, ch = pending
        stride = (w + 1) // 2
        vram = g.read_mem(vseg, pitch * 200)
        if len(vram) == pitch * 200:
            for y in range(min(h, ch)):
                if not (0 <= y0 + y < 200):
                    continue
                for x in range(min(w, cw)):
                    if not (0 <= x0 + x < pitch):
                        continue
                    b = px[y * stride + (x >> 1)]
                    v = (b >> 4) if (x & 1) == 0 else (b & 15)
                    if v == 0:
                        continue
                    s = vram[(y0 + y) * pitch + x0 + x]
                    pairs.setdefault(v, {}).setdefault(s, 0)
                    pairs[v][s] += 1
        pending = None

    ss, ds, si = r["ss"], r["ds"], r["si"] & 0xffff

    def w2(o):
        return int.from_bytes(g.read_mem(ss * 16 + o, 2), "little")

    try:
        _w0, w1, h1, _w3 = struct.unpack("<4H", g.read_mem(ds * 16 + si, 8))
    except Exception:
        continue
    w, h = w1 + 1, h1 + 1
    if not (2 <= w <= 320 and 2 <= h <= 200):
        continue
    # ss:[0c2c..0c32] is the clip rectangle, ss:[1dd5] the destination pitch --
    # assuming 320 was what made the first run sample neighbouring pixels and
    # return the background distribution for every nibble.
    x0, y0, x1, y1 = w2(0x0c2c), w2(0x0c2e), w2(0x0c30), w2(0x0c32)
    pitch = w2(0x1dd5)
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    if not (0 < pitch <= 640 and 0 < cw <= 320 and 0 < ch <= 200):
        continue
    vptr = g.read_mem(ss * 16 + 0x1dbf, 4)      # les di, ss:[1dbf] -- the target
    voff, vseg = struct.unpack("<2H", vptr)
    px = g.read_mem(ds * 16 + si + 8, ((w + 1) // 2) * h)
    if len(px) == ((w + 1) // 2) * h and 0 <= x0 < pitch and 0 <= y0 < 200:
        pending = (vseg * 16 + voff, x0, y0, w, h, px, pitch, cw, ch)

mcp("clear_breakpoints")
print(f"\n{'nibble':>6}  screen byte (count)   [mapping]")
mapping = {}
for v in sorted(pairs):
    top = sorted(pairs[v].items(), key=lambda kv: -kv[1])
    mapping[v] = top[0][0]
    shown = "  ".join(f"{s:3d}({n})" for s, n in top[:4])
    print(f"{v:6d}  {shown}")
if len(mapping) >= 3:
    deltas = {s - v for v, s in mapping.items()}
    print(f"\nnibble -> screen deltas: {sorted(deltas)}")
    print("constant base" if len(deltas) == 1 else "not a constant base -- a 16-entry LUT")
g.cont()

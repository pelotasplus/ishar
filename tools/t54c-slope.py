#!/usr/bin/env python3
"""How far across the screen does an object move per cell of lateral party movement?

Absolute screen position cannot be read off a single frame: a sprite's origin is not the
object's centre -- two lateral-zero observations of the same NPC gave centres 144 and 127 --
so each sprite carries an anchor nobody has measured. A **difference** cancels the anchor,
so this measures the slope instead: hold the distance fixed, step sideways, and record how
far the same sprite moves.

    tools/t54c-slope.py ASSET STEPS [KEY]   e.g. tools/t54c-slope.py bormin.io 4 Right
"""
import json, os, struct, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import ioscan, chains
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
W, H = 320, 200
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:])["result"]
            return j.get("structuredContent", j)

def rows_of(d, off, w, h, base):
    w0 = struct.unpack_from("<H", d, off)[0]
    mode = w0 & 0xFF
    hdr, bpp, _ = ioscan.MODES[mode]
    stride = (w + 1) // 2
    out = []
    for y in range(h):
        r = []
        for x in range(w):
            b = d[off + hdr + y * stride + x // 2]
            nib = (b >> 4) if x % 2 == 0 else (b & 0xF)
            r.append(None if (mode in (0x00, 0x10) and nib == 0) else (base + nib) & 0xFF)
        out.append(r)
    return out

def find(fb, rows, w, h):
    """Exhaustive single-pixel search. Stepping by two once missed an odd-y origin."""
    best = None
    for oy in range(H - h + 1):
        for ox in range(W - w + 1):
            ok = bad = 0
            for y in range(0, h, 2):
                b = (oy + y) * W + ox
                r = rows[y]
                for x in range(0, w, 2):
                    v = r[x]
                    if v is None:
                        continue
                    if fb[b + x] == v:
                        ok += 1
                    else:
                        bad += 1
            if ok > 20 and (best is None or ok / (ok + bad) > best[0]):
                best = (ok / (ok + bad), ox, oy)
    return best

def main():
    name = sys.argv[1]
    steps = int(sys.argv[2])
    key = sys.argv[3] if len(sys.argv) > 3 else "Left"
    d = ioscan.decode(open(os.path.join(GAME, name), "rb").read())[0]
    sprites = sorted((o, w, h) for c in chains.all_chains(d) for o, w, h, _ in c)
    ss = mcp("read_cpu_state")["SS"]
    g = Rsp(st["gdb"])
    print(f"  {'party':>9}  {'sprite':>8} {'size':>8} {'origin':>12}  {'match':>6}  dx")
    prev = {}
    for i in range(steps):
        b = bytearray()
        while len(b) < W * H:
            b += g.read_mem(0xA0000 + len(b), min(4096, W * H - len(b)))
        g.cont()
        fb = bytes(b)
        pos = bytes.fromhex(mcp("read_memory",
                                {"segment": ss, "offset": 0x644c, "length": 2})["Data"])
        for off, w, h in sprites:
            r = find(fb, rows_of(d, off, w, h, 208), w, h)
            if not r or r[0] < 0.9:
                continue
            pct, ox, oy = r
            dx = f"{ox - prev[off][0]:+d}" if off in prev else "-"
            print(f"  ({pos[0]:2},{pos[1]:2})  {off:8} {w:3}x{h:<4} "
                  f"{'(%d,%d)' % (ox, oy):>12}  {pct*100:5.1f}%  {dx}", flush=True)
            prev[off] = (ox, oy)
        if i + 1 < steps:
            subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", key],
                           capture_output=True)
            time.sleep(1.2)

main()

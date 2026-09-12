#!/usr/bin/env python3
"""Which asset does a viewport object's pixels come from, and which sprite?

The viewport blits 1:1 (T54), so at the row step SI points into the source sprite. DS:SI
therefore names the asset and the offset directly -- the framebuffer cannot, because
objects clip and overlap.

At seg_0e97:05f4 a row has just been drawn: DX is its pixel count, BP the rows left, SI
the source row just consumed.
"""
import json, os, subprocess, sys, time, urllib.request
from collections import Counter
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import ioscan, chains
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:])["result"]
            return j.get("structuredContent", j)

def main():
    site = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x05f4
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 40
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    seg = load + 0x0e97
    addr = seg * 16 + site
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
    g = Rsp(st["gdb"])
    drv = os.path.join(os.environ.get("CLAUDE_JOB_DIR", "/tmp"), "tmp", "t55drv.sh")
    os.makedirs(os.path.dirname(drv), exist_ok=True)
    ext = os.environ.get("T55_DRIVER")
    if ext:
        subprocess.Popen([ext])
    else:
        open(drv, "w").write("#!/bin/sh\ncd %s\nfor k in Up Up Down Down; do\n"
                             " tools/ish keys $k >/dev/null 2>&1\n sleep 1.2\ndone\n" % HERE)
        os.chmod(drv, 0o755)
        subprocess.Popen([drv])
    objs, t0 = [], time.time()
    while time.time() - t0 < secs and len(objs) < 400:
        g.cont()
        if g.wait_stop(timeout=secs - (time.time() - t0)) is None:
            break
        r = g.registers()
        if r["ip"] != addr:
            continue
        objs.append((r["ds"], r["si"] & 0xffff, r["dx"] & 0xffff,
                     r["bp"] & 0xffff, r["di"] & 0xffff))
    # one entry per object: the row with the largest BP is its first row
    mcp("clear_breakpoints")
    # read a slice of each distinct source segment while still stopped
    segs = {}
    for ds, si, dx, bp, di in objs:
        segs.setdefault(ds, set()).add(si)
    dumps = {}
    for ds in segs:
        try:
            dumps[ds] = g.read_mem(ds * 16, 0x10000)
        except Exception:
            pass
    g.cont()
    print(f"{len(objs)} rows drawn at seg_0e97:{site:04x}, {len(segs)} source segments")
    assets = {}
    for n in sorted(os.listdir(GAME)):
        if n.lower().endswith(".io"):
            try: assets[n] = ioscan.decode(open(os.path.join(GAME, n), "rb").read())[0]
            except Exception: pass
    seen = Counter()
    for ds, si, dx, bp, di in objs:
        d = dumps.get(ds)
        if not d or si + 64 > len(d):
            continue
        probe = d[si:si + 48]
        if len(set(probe)) < 4:
            continue
        hit = [(n, a.find(probe)) for n, a in assets.items() if a.find(probe) >= 0]
        if len(hit) == 1:
            seen[(hit[0][0], dx, bp)] += 1
    out = Counter()
    SPRITES = {}
    for ds, si, dx, bp, di in objs:
        d = dumps.get(ds)
        if not d or si + 48 > len(d):
            continue
        probe = d[si:si + 48]
        if len(set(probe)) < 4:
            continue
        hit = [(n, a.find(probe)) for n, a in assets.items() if a.find(probe) >= 0]
        if len(hit) != 1:
            out[("?" if not hit else "ambiguous", dx, 0, 0, 0, "-")] += 1
            continue
        n, at = hit[0]
        spr = SPRITES.setdefault(n, sorted((o, w, h) for c in chains.all_chains(assets[n])
                                           for o, w, h, _ in c))
        owner = next(((o, w, h) for o, w, h in spr
                      if o <= at < o + 8 + ((w + 1) // 2) * h), None)
        y, x = divmod(di, 320)
        where = "panel" if x >= 252 else ("bottom bar" if y >= 126 else "VIEWPORT")
        o, w, h = owner if owner else (-1, 0, 0)
        out[(n, dx, o, w, h, where)] += 1
    print(f"  {'asset':<12} {'px/row':>6} {'sprite@':>8} {'size':>9}  where")
    for (n, dx, o, w, h, where), c in out.most_common(16):
        print(f"  {n:<12} {dx:6} {o:8} {w:4}x{h:<4}  {where}  x{c}")

main()

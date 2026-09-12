#!/usr/bin/env python3
"""Locate every UI chrome sprite on screen, framebuffer -> file.

Expanding a sprite and searching the framebuffer for it found nothing (T53): the panel is
composited over, so whole sprites rarely sit intact. Going the other way works -- take a
run of screen pixels, subtract a palette base, repack two per byte, and search the decoded
asset for those bytes.

    tools/t53b-chrome.py                 all chrome assets
    tools/t53b-chrome.py frise.io 208    one asset at one base
"""
import json, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import ioscan, chains
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
W, H = 320, 200
RUNS = (16, 12, 8)           # probe lengths; long is unique, short survives overdraw

def vram():
    g = Rsp(st["gdb"])
    b = bytearray()
    while len(b) < W * H:
        b += g.read_mem(0xA0000 + len(b), min(4096, W * H - len(b)))
    g.cont()
    return bytes(b)

def probe(fb, y, x, base, n):
    px = [fb[y * W + x + i] for i in range(n)]
    if any(p < base or p - base > 15 for p in px):
        return None
    out = bytearray()
    for i in range(0, n - 1, 2):
        out.append(((px[i] - base) << 4) | (px[i + 1] - base))
    return bytes(out)

def main():
    assets = [(sys.argv[1], int(sys.argv[2]))] if len(sys.argv) > 2 else \
             [("frise.io", 208), ("frise.io", 192), ("frise.io", 176),
              ("buste.io", 208)]
    fb = vram()
    cache = {}
    found = {}
    for name, base in assets:
        if name not in cache:
            d = ioscan.decode(open(os.path.join(GAME, name), "rb").read())[0]
            sp = sorted((o, w, h) for c in chains.all_chains(d) for o, w, h, _ in c)
            cache[name] = (d, sp)
        d, sp = cache[name]
        for y in range(0, H):
            for x in range(0, W - 16, 2):
                i = p = None
                for n in RUNS:
                    p = probe(fb, y, x, base, n)
                    if not p or len(set(p)) < 3:
                        continue
                    j = d.find(p)
                    if j >= 0 and d.find(p, j + 1) < 0:
                        i = j
                        break
                if i is None:
                    continue
                owner = None
                for off, sw, sh in sp:
                    w0 = __import__("struct").unpack_from("<H", d, off)[0]
                    hdr, bpp, _ = ioscan.MODES[w0 & 0xFF]
                    size = hdr + ((sw + 1) // 2 if bpp == 4 else sw) * sh
                    if off <= i < off + size:
                        owner = (off, sw, sh, w0 & 0xFF)
                        break
                if not owner:
                    continue
                off, sw, sh, mode = owner
                stride = (sw + 1) // 2
                row = (i - off - ioscan.MODES[mode][0]) // stride
                col = ((i - off - ioscan.MODES[mode][0]) % stride) * 2
                origin = (x - col, y - row)
                key = (name, off, sw, sh, mode, base)
                found.setdefault(key, {}).setdefault(origin, 0)
                found[key][origin] += 1
    # A probe hit is a lead. The check is the whole sprite: expand it at that base and
    # compare every opaque pixel against the screen. The panel came out 90.4% because the
    # game composites over it; noise comes out near chance.
    import struct as _s
    print(f"{'asset':<10} {'offset':>7} {'size':>9} {'mode':>5} {'base':>5} "
          f"{'origin':>12} {'match':>7} {'px':>6}")
    rows = []
    for (name, off, sw, sh, mode, base), origins in found.items():
        d, _ = cache[name]
        hdr, bpp, _ = ioscan.MODES[mode]
        stride = (sw + 1) // 2 if bpp == 4 else sw
        for (ox, oy), votes in origins.items():
            if ox < 0 or oy < 0 or ox + sw > W or oy + sh > H:
                continue
            ok = bad = 0
            for y in range(sh):
                for x in range(sw):
                    b = d[off + hdr + y * stride + x // 2]
                    nib = (b >> 4) if x % 2 == 0 else (b & 0xF)
                    if mode in (0x00, 0x10) and nib == 0:
                        continue
                    v = (base + nib) & 0xFF if bpp == 4 else b
                    if fb[(oy + y) * W + ox + x] == v:
                        ok += 1
                    else:
                        bad += 1
            if ok + bad < 50:
                continue
            rows.append((ok / (ok + bad), name, off, sw, sh, mode, base, ox, oy, ok + bad))
    for pct, name, off, sw, sh, mode, base, ox, oy, npx in sorted(rows, reverse=True):
        if pct < 0.55:
            continue
        print(f"{name:<10} {off:7} {sw:4}x{sh:<4} {mode:#05x} {base:5} "
              f"{'(%d, %d)' % (ox, oy):>12} {pct*100:6.1f}% {npx:6}")

main()

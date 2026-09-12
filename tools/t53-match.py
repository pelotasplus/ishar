#!/usr/bin/env python3
"""Find where each UI sprite is drawn, by matching its pixels against live video memory.

FORMATS 3.17 lists eight positions polled from a redraw but does not say which sprite
belongs at each. This answers that the other way round: take a sprite, expand it to screen
indices at its palette base, and find where those indices actually sit in the framebuffer.

Transparent nibbles are skipped in the comparison -- they are whatever was underneath.
"""
import json, os, struct, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import ioscan
from ioscan import decode, extract, MODES

st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
W, H = 320, 200

def vram():
    g = Rsp(st["gdb"])
    b = bytearray()
    while len(b) < W * H:
        b += g.read_mem(0xA0000 + len(b), min(4096, W * H - len(b)))
    g.cont()
    return bytes(b)

def expand(d, off, w, h, base):
    """-> rows of screen indices, None where transparent."""
    w0 = struct.unpack_from("<H", d, off)[0]
    mode = w0 & 0xFF
    hdr, bpp, _ = MODES[mode]
    p = off + hdr
    rows = []
    for y in range(h):
        row = []
        if bpp == 8:
            for x in range(w):
                v = d[p + y * w + x]
                row.append(None if mode == 0x14 and v == 0 else v)
        else:
            stride = (w + 1) // 2
            for x in range(w):
                byte = d[p + y * stride + x // 2]
                nib = (byte >> 4) if x % 2 == 0 else (byte & 0xF)
                keyed = mode in (0x00, 0x10)
                row.append(None if (keyed and nib == 0) else (base + nib) & 0xFF)
        rows.append(row)
    return rows

def find(fb, rows, w, h, minrun=12):
    """Locate the sprite in the framebuffer using its longest opaque run as a probe."""
    best = None
    for y0, row in enumerate(rows):
        run, start = 0, None
        for x in range(w):
            if row[x] is not None:
                if run == 0:
                    start = x
                run += 1
                if run >= minrun:
                    best = (y0, start, run)
                    break
            else:
                run = 0
        if best:
            break
    if not best:
        return []
    ry, rx, rn = best
    pat = bytes(rows[ry][rx:rx + rn])
    hits = []
    i = fb.find(pat)
    while i >= 0 and len(hits) < 400:
        sy, sx = divmod(i, W)
        ox, oy = sx - rx, sy - ry
        if 0 <= ox and ox + w <= W and 0 <= oy and oy + h <= H:
            ok = bad = 0
            for y in range(h):
                base = (oy + y) * W + ox
                r = rows[y]
                for x in range(w):
                    v = r[x]
                    if v is None:
                        continue
                    if fb[base + x] == v:
                        ok += 1
                    else:
                        bad += 1
            if ok + bad and ok / (ok + bad) > 0.98:
                hits.append((ox, oy, ok, bad))
        i = fb.find(pat, i + 1)
    return hits

def main():
    fb = vram()
    for name in sys.argv[1:] or ["frise.io", "buste.io"]:
        d = decode(open(os.path.join(GAME, name), "rb").read())[0]
        print(f"\n{name}")
        for off, w, h in extract(d):
            w0, _, _, w3 = struct.unpack_from("<4H", d, off)
            mode = w0 & 0xFF
            bases = [w3 & 0xFF] if mode in (0x10, 0x12) else [0]
            if mode in (0x10, 0x12):
                bases += [b for b in (208, 192, 176, 0) if b != bases[0]]
            for b in bases:
                hits = find(d and expand(d, off, w, h, b), w, h) if False else \
                       find(fb, expand(d, off, w, h, b), w, h)
                if hits:
                    for x, y, ok, bad in hits[:4]:
                        print(f"  off {off:6} {w:3}x{h:<3} mode {mode:#04x} base {b:3}"
                              f"  ->  ({x:3},{y:3})  {ok} px, {bad} wrong")
                    break

main()

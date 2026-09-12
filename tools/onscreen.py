#!/usr/bin/env python3
"""Inventory: which sprites from which assets are on screen right now.

The viewport blits 1:1 (T54), so a viewport sprite DOES appear verbatim in video memory --
which contradicts the older note that it never could. Each sprite's longest opaque run is
used as a probe, then any hit is verified over the whole sprite.
"""
import json, os, struct, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import ioscan, chains
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

def rows_of(d, off, w, h, base):
    w0 = struct.unpack_from("<H", d, off)[0]
    mode = w0 & 0xFF
    hdr, bpp, _ = ioscan.MODES[mode]
    stride = (w + 1) // 2 if bpp == 4 else w
    out = []
    for y in range(h):
        r = []
        for x in range(w):
            if bpp == 8:
                v = d[off + hdr + y * stride + x]
                r.append(None if mode == 0x14 and v == 0 else v)
            else:
                b = d[off + hdr + y * stride + x // 2]
                nib = (b >> 4) if x % 2 == 0 else (b & 0xF)
                r.append(None if (mode in (0x00, 0x10) and nib == 0) else (base + nib) & 0xFF)
        out.append(r)
    return out

def main():
    names = sys.argv[1:] or sorted(n for n in os.listdir(GAME) if n.lower().endswith(".io"))
    fb = vram()
    for name in names:
        try:
            d = ioscan.decode(open(os.path.join(GAME, name), "rb").read())[0]
        except Exception:
            continue
        for off, w, h in sorted((o, sw, sh) for c in chains.all_chains(d) for o, sw, sh, _ in c):
            if w < 8 or h < 8:
                continue
            for base in range(0, 256, 16):
                rows = rows_of(d, off, w, h, base)
                # A ragged sprite -- a tree canopy -- may have no long opaque run in any
                # row. Narrow sprites get a shorter probe; below 8 the match is not unique.
                need = 14 if w >= 32 else max(8, w // 2)
                probe = None
                for y in range(h):
                    run, start = 0, 0
                    for x in range(w):
                        if rows[y][x] is not None:
                            if run == 0:
                                start = x
                            run += 1
                            if run >= need:
                                probe = (y, start, bytes(rows[y][start:start + need]))
                                break
                        else:
                            run = 0
                    if probe:
                        break
                if not probe or len(set(probe[2])) < 3:
                    continue
                i = fb.find(probe[2])
                if i < 0:
                    continue
                sy, sx = divmod(i, W)
                ox, oy = sx - probe[1], sy - probe[0]
                if ox < 0 or oy < 0 or ox + w > W or oy + h > H:
                    continue
                ok = bad = 0
                for y in range(h):
                    b0 = (oy + y) * W + ox
                    for x in range(w):
                        v = rows[y][x]
                        if v is None:
                            continue
                        ok += fb[b0 + x] == v
                        bad += fb[b0 + x] != v
                if ok + bad and ok / (ok + bad) > 0.95:
                    print(f"  {name:<14} @{off:<6} {w:3}x{h:<3} base {base:3} -> "
                          f"({ox:3},{oy:3})  {ok*100.0/(ok+bad):5.1f}%  {ok+bad} px", flush=True)
                    break

main()

#!/usr/bin/env python3
"""What is drawn at one screen pixel? Search every asset at every palette base.

The framebuffer->file direction is the one that works for chrome (T53). This widens it:
instead of assuming an asset and a base, take a run of screen pixels and try all of both.

    tools/whichsprite.py X Y [assets...]
"""
import json, os, struct, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import ioscan, chains
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
W = 320

def vram():
    g = Rsp(st["gdb"])
    b = bytearray()
    while len(b) < W * 200:
        b += g.read_mem(0xA0000 + len(b), min(4096, W * 200 - len(b)))
    g.cont()
    return bytes(b)

def main():
    x, y = int(sys.argv[1]), int(sys.argv[2])
    names = sys.argv[3:] or ["frise.io", "buste.io", "objet.io", "main.io"]
    fb = vram()
    print(f"pixels at ({x},{y}): {bytes(fb[y*W+x:y*W+x+16]).hex()}")
    for name in names:
        d = ioscan.decode(open(os.path.join(GAME, name), "rb").read())[0]
        sp = sorted((o, w, h) for c in chains.all_chains(d) for o, w, h, _ in c)
        for base in range(0, 256, 16):
            px = [fb[y * W + x + i] for i in range(16)]
            if any(p < base or p - base > 15 for p in px):
                continue
            pat = bytes(((px[i] - base) << 4) | (px[i + 1] - base) for i in range(0, 16, 2))
            if len(set(pat)) < 3:
                continue
            i = d.find(pat)
            if i < 0:
                continue
            owner = None
            for off, sw, sh in sp:
                w0 = struct.unpack_from("<H", d, off)[0]
                hdr, bpp, _ = ioscan.MODES[w0 & 0xFF]
                if off <= i < off + hdr + ((sw + 1) // 2) * sh:
                    owner = (off, sw, sh, w0 & 0xFF, hdr)
                    break
            tag = (f"sprite @{owner[0]} {owner[1]}x{owner[2]} mode {owner[3]:#04x}"
                   if owner else "outside any chain")
            print(f"  {name} base {base:3} -> offset {i}  {tag}")

main()

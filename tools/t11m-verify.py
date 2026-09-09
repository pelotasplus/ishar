#!/usr/bin/env python3
"""
T11m acceptance: does the static extraction reproduce the emulator's screen?

Takes sprites extracted offline by tools/ioscan.py, maps each nibble through
`group*16 + nibble` (group = high byte of header word 0), and looks for that
exact run of palette indices in the live framebuffer. A hit means the extractor
predicted the bytes the game put on screen -- not that the picture merely looks
plausible.
"""
import json, os, struct, sys, importlib.util

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp

spec = importlib.util.spec_from_file_location("ioscan", os.path.join(HERE, "tools", "ioscan.py"))
ioscan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ioscan)
_ns = {}
exec(open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0], _ns)
decode = _ns["decode"]

GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
g = Rsp(st["gdb"])
vram = g.read_mem(0xA0000, 320 * 200)
print(f"framebuffer: {len(vram)} bytes")

for fname in sys.argv[1:] or ["fond.io"]:
    data = decode(open(os.path.join(GAME, fname), "rb").read())[0]
    sprites = ioscan.extract(data)
    end = sprites[-1][0] + 8 + ((sprites[-1][1] + 1) // 2) * sprites[-1][2] if sprites else 0
    pal = ioscan.find_palette(data, end)
    print(f"\n{fname}: {len(sprites)} sprites, palette at {pal[0] if pal else None}")
    for off, w, h in sprites:
        group = struct.unpack_from("<H", data, off)[0] >> 8
        base = group * 16 if group < 16 else 0
        stride = (w + 1) // 2
        # predicted index for every pixel of the sprite
        rows = []
        for y in range(h):
            rows.append([((data[off + 8 + y * stride + (x >> 1)] >> 4) if (x & 1) == 0
                          else (data[off + 8 + y * stride + (x >> 1)] & 15)) for x in range(w)])
        bestscore, bestpos = 0, None
        for sy in range(0, 200 - h + 1):
            for sx in range(0, 320 - w + 1):
                hit = tot = 0
                for y in range(0, h, max(1, h // 12)):
                    r = rows[y]
                    vb = (sy + y) * 320 + sx
                    for x in range(0, w, max(1, w // 12)):
                        if r[x] == 0:
                            continue
                        tot += 1
                        if vram[vb + x] == base + r[x]:
                            hit += 1
                if tot >= 8 and hit / tot > bestscore:
                    bestscore, bestpos = hit / tot, (sx, sy)
        if bestscore > 0.6 and bestpos:
            sx, sy = bestpos
            hit = tot = 0
            for y in range(h):
                for x in range(w):
                    if rows[y][x] == 0:
                        continue
                    tot += 1
                    hit += vram[(sy + y) * 320 + sx + x] == base + rows[y][x]
            print(f"  {w}x{h} group {group:2d} at ({sx},{sy}): "
                  f"{hit}/{tot} = {100*hit/tot:.1f}% of opaque pixels match the screen")

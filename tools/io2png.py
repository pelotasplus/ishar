#!/usr/bin/env python3
"""
Render a decoded .io asset to PNG.

What is established (FORMATS.md §3.7): a decoded asset holds **8-bit palette
indices**, byte for byte the same values the game writes to VGA memory — proven
by matching `logo.io`'s decoded bytes against the emulator's framebuffer while
the logo was on screen. What is NOT established is the geometry: the width is
per-asset and the header that carries it has not been read yet, so this tool
takes the width as an argument and defaults to the 144 measured for logo.io.

    tools/io2png.py logo.io out.png --width 144 --skip 296
    tools/io2png.py logo.io out.png --width 144 --palette .ish/logo-palette.json
    tools/io2png.py --grid foret.io out.png --width 320   # try a width quickly

Without a palette it renders greyscale, which is enough to see shapes and judge
whether a width is right: a wrong width shears the picture diagonally.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import png  # noqa: E402

_src = open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0]
_ns = {}
exec(_src, _ns)
decode = _ns["decode"]


def load_palette(path):
    """The DAC as Spice86 reports it: 256 entries with 8-bit R/G/B."""
    d = json.load(open(path))
    entries = d["Entries"] if isinstance(d, dict) else d
    pal = [(0, 0, 0)] * 256
    for e in entries:
        pal[e["Index"]] = (e["R"], e["G"], e["B"])
    return pal


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit(__doc__)
    src, dst = args[0], args[1]
    if not os.path.exists(src):
        src = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com", src)
    width = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 144
    skip = int(sys.argv[sys.argv.index("--skip") + 1]) if "--skip" in sys.argv else 0
    pal = (load_palette(sys.argv[sys.argv.index("--palette") + 1])
           if "--palette" in sys.argv else [(i, i, i) for i in range(256)])

    data = decode(open(src, "rb").read())[0][skip:]
    height = len(data) // width
    if height == 0:
        sys.exit(f"{len(data)} bytes is less than one row of {width}")
    rows = [[pal[data[y * width + x]] for x in range(width)] for y in range(height)]
    png.write(dst, rows)
    print(f"{os.path.basename(src)}: {len(data)} bytes -> {dst}  {width}x{height}"
          f"  ({len(data) % width} bytes left over)")


main()

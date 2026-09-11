#!/usr/bin/env python3
"""Render an asset's full-screen 320x200 pages.

Some assets carry no sprite chain at all: they are whole VGA pages, stored at the
END of the decoded blob in 64,000-byte units, preceded by a palette record and a
short script. dead.io is one -- 65,984 bytes = 1,984 + 64,000 -- and it renders
pixel-identical to captures/t44-kill.png, which is how the layout was established.

Only dead.io and auteur.io are known to be laid out this way. Assets that carry a
sprite chain also carry palette records, and anchoring a page off one of those gives
noise -- presen.io, iboishar.io and stage.io all do. Check ioscan finds no sprites
before believing a page.

    tools/fullscreen.py dead.io out-dir
"""
import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import png
_ns = {}
exec(open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0], _ns)
decode = _ns["decode"]
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
PAGE = 320 * 200

def layout(d):
    """(palette, first page offset). The page follows the palette record, not the
    end of the blob: dead.io's page is at 1972 and 12 bytes trail it, so anchoring
    on len(d) - 64000 lands 12 bytes late and the match drops to 32%.

        fe ff 00 00 | 768 palette bytes | 8 bytes | 320x200 page
    """
    m = d.find(b"\xfe\xff\x00\x00")
    if m < 0:
        return [(i, i, i) for i in range(256)], None, None
    p = m + 4
    pal = [tuple(d[p + i * 3:p + i * 3 + 3]) for i in range(256)]
    return pal, p, p + 768 + 8

def main():
    name, outdir = sys.argv[1], sys.argv[2]
    d = decode(open(os.path.join(GAME, name), "rb").read())[0]
    os.makedirs(outdir, exist_ok=True)
    pal, pat, first = layout(d)
    offs = [] if first is None else [o for o in range(first, len(d) - PAGE + 1, PAGE)]
    stem = os.path.splitext(name)[0].lower()
    for i, off in enumerate(offs):
        rows = [[pal[d[off + y * 320 + x]] for x in range(320)] for y in range(200)]
        out = os.path.join(outdir, f"{stem}-page{i}.png")
        png.write(out, rows)
        print(f"{name}: page {i} at {off} -> {out} (palette at {pat})")
    if not offs:
        print(f"{name}: {len(d)} bytes, no palette record, so no page anchor")

main()

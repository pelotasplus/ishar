#!/usr/bin/env python3
"""
Extract sprites from a decoded .io asset by walking the sprite chain.

Sprites are **4 bits per pixel** (FORMATS.md 3.10) and are stored back to back:
an 8-byte header [word0, width-1, height-1, word3] followed by
`ceil(width/2) * height` bytes, then the next header. Measured on 30 sprites
captured live from the blitter, where the gap between consecutive sprites in a
buffer matched `8 + ceil(w/2)*h` in every case.

Assuming 8bpp is what made every earlier attempt fail: the chain broke at the
first sprite, so it looked as though there were no chain and no directory.

    tools/ioscan.py logo.io out/
    tools/ioscan.py --all out/
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
sys.path.insert(0, os.path.join(HERE, "tools"))
import png  # noqa: E402

_src = open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0]
_ns = {}
exec(_src, _ns)
decode = _ns["decode"]

MAX_W, MAX_H = 336, 208


def rec(data, off):
    """Size of the sprite record at `off`, or None if it cannot be one."""
    if off + 8 > len(data):
        return None
    _, w1, h1, _w3 = struct.unpack_from("<4H", data, off)
    w, h = w1 + 1, h1 + 1
    if not (2 <= w <= MAX_W and 2 <= h <= MAX_H):
        return None
    n = 8 + ((w + 1) // 2) * h
    if off + n > len(data):
        return None
    return n, w, h


def chains(data):
    """Longest valid chain reachable from each offset, computed once."""
    best = {}
    for off in range(len(data) - 8, -1, -2):
        r = rec(data, off)
        best[off] = 1 + best.get(off + r[0], 0) if r else 0
    return best


def walk(data, start):
    out, off = [], start
    while True:
        r = rec(data, off)
        if not r:
            break
        n, w, h = r
        out.append((off, w, h))
        off += n
    return out


def extract(data):
    """The chain that explains the most of the file wins."""
    best = chains(data)
    starts = sorted(best, key=lambda o: (-best[o], o))
    if not starts or best[starts[0]] < 2:
        return []
    return walk(data, starts[0])


def find_palette(data, taken):
    """256 8-bit RGB triples (FORMATS.md 3.9), outside the sprite data."""
    cand = None
    for off in range(0, len(data) - 768, 2):
        if data[off] or data[off + 1] or data[off + 2]:
            continue
        if any(off < e and s < off + 768 for s, e in taken):
            continue
        chunk = data[off:off + 768]
        n = len({chunk[i:i + 3] for i in range(0, 768, 3)})
        if cand is None or n > cand[0]:
            cand = (n, off)
    if not cand or cand[0] < 24:
        return None
    off = cand[1]
    c = data[off:off + 768]
    return off, [tuple(c[i:i + 3]) for i in range(0, 768, 3)]


def render(data, off, w, h, pal):
    stride = (w + 1) // 2
    base = off + 8
    rows = []
    for y in range(h):
        r = []
        for x in range(w):
            b = data[base + y * stride + (x >> 1)]
            v = (b >> 4) if (x & 1) == 0 else (b & 15)
            r.append((0, 255, 0) if v == 0 else pal[v])
        rows.append(r)
    return rows


def do_file(path, outdir):
    name = os.path.splitext(os.path.basename(path))[0].lower()
    try:
        data = decode(open(path, "rb").read())[0]
    except Exception as e:
        return f"{name}: decode failed ({e})"
    sprites = extract(data)
    taken = [(o, o + 8 + ((w + 1) // 2) * h) for o, w, h in sprites]
    found = find_palette(data, taken)
    pal = found[1] if found else [(i * 16 % 256,) * 3 for i in range(256)]
    os.makedirs(outdir, exist_ok=True)
    for off, w, h in sprites:
        png.write(os.path.join(outdir, f"{name}-{off:06d}-{w}x{h}.png"),
                  render(data, off, w, h, pal))
    covered = sum(e - s for s, e in taken)
    return (f"{name}: {len(sprites):3d} sprites, "
            f"{100 * covered // max(1, len(data)):3d}% of {len(data)} bytes, "
            f"palette {found[0] if found else '-'}")


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not argv:
        sys.exit(__doc__)
    if "--all" in sys.argv:
        for f in sorted(x for x in os.listdir(GAME) if x.lower().endswith(".io")):
            print(do_file(os.path.join(GAME, f), argv[0]), flush=True)
    else:
        src = argv[0] if os.path.exists(argv[0]) else os.path.join(GAME, argv[0])
        print(do_file(src, argv[1] if len(argv) > 1 else "."))


if __name__ == "__main__":
    main()

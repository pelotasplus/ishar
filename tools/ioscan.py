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

# Word 0's low byte is a pixel-format selector, dispatched by sprite_mode_dispatch
# at seg_0e97:0a30 (FORMATS.md 3.10). It decides the header length, the bit depth and
# where the palette base comes from -- not a colour count, as it was first read.
#   mode -> (header bytes, bits per pixel, base from word 3?)
MODES = {0x00: (6, 4, False),   # seg_0e97:0b40 -- `mov bh,0`, `add si,6`
         0x10: (8, 4, True),    # seg_0e97:0b4c -- 742 of ~800 sprites
         0x12: (8, 4, True),    # seg_0e97:0aca
         0x14: (8, 8, False),   # seg_0e97:0a84 -- lodsb/test/stosb, 0 transparent
         0x16: (8, 8, False)}   # seg_0e97:0a5b -- rep movsw, opaque


def geometry(w0, w, h):
    """(header, stride, size) for a sprite, or None if word 0 names no known mode."""
    m = MODES.get(w0 & 0xff)
    if m is None:
        return None
    hdr, bpp, _ = m
    stride = w if bpp == 8 else (w + 1) // 2
    return hdr, stride, hdr + stride * h


def rec(data, off):
    """Size of the sprite record at `off`, or None if it cannot be one."""
    if off + 8 > len(data):
        return None
    w0, w1, h1, _w3 = struct.unpack_from("<4H", data, off)
    w, h = w1 + 1, h1 + 1
    if not (2 <= w <= MAX_W and 2 <= h <= MAX_H):
        return None
    # Word 0 is `flags | group` in the high byte and a small constant in the low
    # byte (16 for 742 of ~800 sprites -- the colour count). Across the whole game
    # the flag nibble is only ever 0x00 (743), 0x10 (9) or 0x20 (50); 0x30, 0x40,
    # 0x60 and 0xf0 appear a handful of times each and are the chain having lost
    # sync. Rejecting those here keeps a bad chain from scoring well in the first
    # place, rather than filtering its output afterwards.
    if (w0 >> 8) & 0xf0 not in (0x00, 0x10, 0x20):
        return None
    g = geometry(w0, w, h)
    if g is None:
        return None
    n = g[2]
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


def palette_score(data, off, floor=0):
    """A VGA palette here is 16 sub-palettes of 16, and groups 1..15 each start
    with white then black. That signature is what makes this a detector rather
    than a guess: it was validated against three offsets established
    independently -- fond.io 12108 and geren.io 6684 (both matched the live DAC
    byte for byte while that scene was on screen) and logo.io 992 (FORMATS 3.9)."""
    s = 0
    for k in range(1, 16):
        b = off + k * 48
        if data[b] > 250 and data[b + 1] > 250 and data[b + 2] > 250:
            s += 1
        if data[b + 3] < 6 and data[b + 4] < 6 and data[b + 5] < 6:
            s += 1
        if s + 2 * (15 - k) < floor:      # cannot still reach the bar
            return s
    return s


PAL_MARK = b"\xfe\xff\x00\x00"


def palettes(data):
    """Every palette in the file, found by its 4-byte record header (T11m4).

    A bank record is `fe ff 00 00` followed by 768 bytes of 8-bit RGB, so palettes
    can be enumerated from the structure instead of guessed at by signature. This
    recovers exactly the offsets established independently against the live DAC --
    geren.io 6684, fond.io 12108, ftemple.io 16244, frise.io 34700 -- and it drops
    the artefacts the signature scan produced: geren.io has 7 palettes, not the 12
    a white/black scan reported, the extra five each sitting 48 bytes (one group)
    before a real one.

    The marker alone is NOT sufficient: `fe ff 00 00` occurs freely inside pixel
    data, and of 80 raw hits across the game only 17 are palettes. Each candidate is
    therefore confirmed against the independent white/black group signature, which
    is what makes this an enumerator rather than another guess.
    """
    out, pos = [], data.find(PAL_MARK)
    while pos >= 0:
        o = pos + 4
        if o + 768 <= len(data) and data[o] < 8 and data[o + 1] < 8 and data[o + 2] < 8 \
                and palette_score(data, o) >= 20:
            out.append(o)
        pos = data.find(PAL_MARK, pos + 1)
    return out


def find_palette(data, chain_end=0, need_full=False):
    """Files carry more than one palette -- fond.io has a valid block at 556 and
    another at 12108, and the live one was 12108. The one in use sits just past
    the sprite chain, so prefer that and fall back to the best-scoring block."""
    # The signature repeats every 48 bytes, so a block shifted by whole groups
    # scores just as well -- fond.io came back 48 early and geren.io 144 early.
    # Entry 0 of a real palette is black (index 0 is the transparent colour),
    # while a shifted candidate starts on some group's white, which pins it.
    marked = palettes(data)
    if marked:
        after = [o for o in marked if o >= chain_end]
        off = (after or marked)[0]
        c = data[off:off + 768]
        return off, [tuple(c[i:i + 3]) for i in range(0, 768, 3)]
    # Fallback for files whose palette carries no record header -- logo.io keeps one
    # at 992 that is verified against the framebuffer but unmarked.
    cands = []
    limit = len(data) - 768
    pos = data.find(b"\x00\x00\x00")
    while 0 <= pos <= limit:
        # Relaxing this bar for 8bpp files was tried, to reach logo.io's unmarked
        # palette at 992: it picked 34196 instead and inflated "has its own palette"
        # from 9 files to 21. Precision wins -- logo.io's palette is documented in
        # FORMATS.md 3.9 and can be passed explicitly.
        s = palette_score(data, pos, 24)
        if s >= 24:
            cands.append((pos, s))
        pos = data.find(b"\x00\x00\x00", pos + 1)
    # No weak fallback: a file with no palette of its own borrows one from the
    # bank, which is what the game does. Guessing at the best-scoring block in
    # such a file is what produced the arbitrary colours.
    # Nothing that had a marker reaches here. Lowering this bar to catch logo.io's
    # unmarked palette (992, verified against the framebuffer, but only 16/30) was
    # tried and made things worse: 71 files matched instead of 9, mostly noise.
    # logo.io is the 8bpp asset ioscan cannot render correctly anyway (3.10), so it
    # falls back to the bank and its real palette is documented in 3.9.
    if not cands:
        return None

    # Overlapping candidates 48 or 144 bytes early still satisfy the black-start
    # rule (geren.io scored one at 6540 as well as the true 6684), and a shifted
    # candidate is always the earlier one, so take the last.
    after = [c for c in cands if c[0] >= chain_end]
    off = (after or cands)[-1][0]
    c = data[off:off + 768]
    return off, [tuple(c[i:i + 3]) for i in range(0, 768, 3)]


def render(data, off, w, h, pal):
    """A 4bpp index is `group * 16 + nibble`. The DAC is 16 sub-palettes of 16
    (measured in-game: every group starts white, black, then a ramp), and the
    group is `word3 >> 4`; word3's low nibble is a per-sprite index (a distance step
    in the 3D view). Word 0 carries flags and a colour count, not the group.
    Rendering with group 0 for everything is what left the shapes right and the
    colours wrong."""
    # The group is in word 3, not word 0 (T11r). buste.io's portraits carry
    # word3 = 0x60, 0x70 ... 0xd0 -- exactly group*16 -- and the portrait at 14802
    # is legible only at group 6, which is 0x60 >> 4. The same field explains the
    # perspective sequence seen live: word3 0xa2, 0xa3, 0xa4, 0xa5 is group 10 with
    # a distance index in the low nibble.
    w0, _, _, w3 = struct.unpack_from("<4H", data, off)
    hdr, stride, _ = geometry(w0, w, h)
    bpp = MODES[w0 & 0xff][1]
    # The base is word 3's LOW BYTE added directly (seg_0e97:0b4c: mov al,[si+6];
    # mov bh,al), and that byte is already group*16. Mode 0 forces it to zero.
    pbase = (w3 & 0xff) if MODES[w0 & 0xff][2] else 0
    base = off + hdr
    rows = []
    for y in range(h):
        r = []
        for x in range(w):
            if bpp == 8:
                v = data[base + y * stride + x]
                r.append((0, 255, 0) if v == 0 else pal[v])
                continue
            b = data[base + y * stride + (x >> 1)]
            v = (b >> 4) if (x & 1) == 0 else (b & 15)
            r.append((0, 255, 0) if v == 0 else pal[(pbase + v) & 0xff])
        rows.append(r)
    return rows


_BANK = []


def bank():
    """geren.io is the game's palette bank: 12 unique 768-byte blocks, four of
    which are byte-identical to the palettes found inside scene files
    (fond -> geren#0, fcave/fcave2 -> geren#2, ftemple -> geren#11, frise ->
    gerdep#0). Assets that carry no palette of their own -- about 100 of 110 --
    borrow one, so the bank is a far better default than the best-scoring block
    in a file that has none. Which entry belongs to which sprite is T11m2; until
    that lands, entry 0 (the outdoor scene) is the placeholder."""
    if _BANK:
        return _BANK
    for name in ("geren.io", "gerdep.io"):
        try:
            d = decode(open(os.path.join(GAME, name), "rb").read())[0]
        except Exception:
            continue
        limit, pos = len(d) - 768, d.find(b"\x00\x00\x00")
        while 0 <= pos <= limit:
            if palette_score(d, pos, 24) >= 24:
                b = bytes(d[pos:pos + 768])
                if b not in _BANK:
                    _BANK.append(b)
            pos = d.find(b"\x00\x00\x00", pos + 1)
    return _BANK


def bank_palette(n=0):
    b = bank()
    if not b:
        return None
    c = b[min(n, len(b) - 1)]
    return [tuple(c[i:i + 3]) for i in range(0, 768, 3)]


def do_file(path, outdir, bank_index=0):
    name = os.path.splitext(os.path.basename(path))[0].lower()
    try:
        data = decode(open(path, "rb").read())[0]
    except Exception as e:
        return f"{name}: decode failed ({e})"
    sprites = extract(data)
    taken = []
    for o, w, h in sprites:
        g = geometry(struct.unpack_from("<H", data, o)[0], w, h)
        taken.append((o, o + g[2]))
    chain_end = taken[-1][1] if taken else 0
    deep = any(MODES[struct.unpack_from("<H", data, o)[0] & 0xff][1] == 8
               for o, _, _ in sprites)
    found = find_palette(data, chain_end, need_full=deep)
    if found:
        pal, where = found[1], str(found[0])
    else:
        pal, where = bank_palette(bank_index), f"bank#{bank_index}"
        if pal is None:
            pal, where = [(i * 16 % 256,) * 3 for i in range(256)], "grey"
    os.makedirs(outdir, exist_ok=True)
    for off, w, h in sprites:
        png.write(os.path.join(outdir, f"{name}-{off:06d}-{w}x{h}.png"),
                  render(data, off, w, h, pal))
    covered = sum(e - s for s, e in taken)
    return (f"{name}: {len(sprites):3d} sprites, "
            f"{100 * covered // max(1, len(data)):3d}% of {len(data)} bytes, "
            f"palette {where}")


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not argv:
        sys.exit(__doc__)
    n = 0
    if "--bank" in sys.argv:
        n = int(sys.argv[sys.argv.index("--bank") + 1])
    if "--all" in sys.argv:
        for f in sorted(x for x in os.listdir(GAME) if x.lower().endswith(".io")):
            print(do_file(os.path.join(GAME, f), argv[0], n), flush=True)
    else:
        src = argv[0] if os.path.exists(argv[0]) else os.path.join(GAME, argv[0])
        print(do_file(src, argv[1] if len(argv) > 1 else ".", n))


if __name__ == "__main__":
    main()

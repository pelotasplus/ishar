#!/usr/bin/env python3
"""
Minimal PNG read/write, so screen work needs no third-party imaging library.

Only what this project uses: 8-bit RGB/RGBA/greyscale/palette, no interlace.
Written because comparing a render against an emulator screenshot is the
acceptance test for M3 and M4, and that test cannot depend on a library that
may or may not be installed.

    from png import read, write, crop, diff
"""
import struct
import zlib


def read(path):
    """-> (width, height, pixels) with pixels a list of (r,g,b) rows-major."""
    d = open(path, "rb").read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    pos, idat, pal, trns = 8, bytearray(), None, None
    w = h = depth = ctype = None
    while pos < len(d):
        ln = struct.unpack_from(">I", d, pos)[0]
        typ = d[pos + 4:pos + 8]
        body = d[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if interlace:
                raise ValueError("interlaced PNG not supported")
            if depth != 8:
                raise ValueError(f"bit depth {depth} not supported")
        elif typ == b"PLTE":
            pal = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(bytes(idat))
    stride = w * channels
    out, prev = [], bytearray(stride)
    p = 0
    for _ in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if f == 1:
                line[i] = (line[i] + a) & 0xFF
            elif f == 2:
                line[i] = (line[i] + b) & 0xFF
            elif f == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 0xFF
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        prev = line
        row = []
        for x in range(w):
            px = line[x * channels:(x + 1) * channels]
            if ctype == 3:
                row.append(pal[px[0]] if pal else (px[0],) * 3)
            elif ctype in (0, 4):
                row.append((px[0],) * 3)
            else:
                row.append((px[0], px[1], px[2]))
        out.append(row)
    return w, h, out


def write(path, pixels):
    h = len(pixels)
    w = len(pixels[0])
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for r, g, b in row:
            raw += bytes((r, g, b))
    def chunk(typ, body):
        return (struct.pack(">I", len(body)) + typ + body
                + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def crop(pixels, x, y, w, h):
    return [row[x:x + w] for row in pixels[y:y + h]]


def diff(a, b):
    """-> (differing pixel count, total). Sizes must match."""
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        raise ValueError(f"size mismatch: {len(a[0])}x{len(a)} vs {len(b[0])}x{len(b)}")
    bad = sum(1 for ra, rb in zip(a, b) for pa, pb in zip(ra, rb) if pa != pb)
    return bad, len(a) * len(a[0])

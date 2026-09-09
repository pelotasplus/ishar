#!/usr/bin/env python3
"""
Decode Ishar's .io asset container.

Transcribed from the decoder at seg_0000:7a79 and its helpers, annotated in
ishar.chani. Structure (FORMATS.md §3.0, §3.2):

    header  u16 size            total, headers included
            u16 mode            high byte & 0xfe selects the pass count
            u16 is_catalogue    0 -> a 16-byte directory follows

    passes  1 if mode 0x80, 2 if 0xa0, else 8

Each pass runs an RLE stream and writes every `stride`-th output byte, pass p
starting at offset p -- so the passes interleave. A control byte c below 0x80
copies c literal bytes; c >= 0x80 repeats the next byte (c & 0x7f) times. The
pass ends when the output pointer runs past the end, which in the original is a
bounds check on DS:SI rather than a counter.

    tools/io.py <file> [--out raw.bin]
    tools/io.py --all              decode every asset, report what round-trips
"""
import os
import struct
import sys

HEADER = 6
DIRECTORY = 16


def stride_for(mode):
    return 1 if mode == 0x80 else 2 if mode == 0xA0 else 8


def decode(data):
    """-> (out, info). Raises ValueError when the stream does not add up."""
    if len(data) < HEADER:
        raise ValueError("shorter than a header")
    size, mode_word, is_catalogue = struct.unpack_from("<HHH", data, 0)
    mode = (mode_word >> 8) & 0xFE
    header_len = HEADER + (DIRECTORY if is_catalogue == 0 else 0)
    out_len = size - header_len
    info = {"size": size, "mode": mode, "is_catalogue": is_catalogue == 0,
            "stride": stride_for(mode), "out_len": out_len,
            "directory": (list(struct.unpack_from("<8H", data, HEADER))
                          if is_catalogue == 0 else None)}
    if out_len <= 0:
        raise ValueError(f"header says {size} bytes with a {header_len}-byte header")

    payload = data[header_len:]
    stride = info["stride"]
    out = bytearray(out_len)
    src = 0
    for p in range(stride):
        di = p
        while di < out_len:
            if src >= len(payload):
                raise ValueError(f"input exhausted in pass {p} at output {di}")
            c = payload[src]
            src += 1
            if c & 0x80:                       # run: repeat one byte
                n = c & 0x7F
                if src >= len(payload):
                    raise ValueError("input exhausted reading a run byte")
                b = payload[src]
                src += 1
                for _ in range(n):
                    if di >= out_len:
                        break
                    out[di] = b
                    di += stride
            else:                              # literal run
                for _ in range(c):
                    if di >= out_len or src >= len(payload):
                        break
                    out[di] = payload[src]
                    src += 1
                    di += stride
    info["consumed"] = src
    info["left_over"] = len(payload) - src
    return bytes(out), info


def main():
    if "--all" in sys.argv:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        game = os.path.join(here, "ishar_legend_of_the_fortress_DOSGamer.com")
        ok = bad = 0
        for name in sorted(os.listdir(game)):
            if not name.lower().endswith((".io", ".fic")):
                continue
            data = open(os.path.join(game, name), "rb").read()
            try:
                out, info = decode(data)
            except ValueError as e:
                print(f"  {name:<14} FAILED  {e}")
                bad += 1
                continue
            ok += 1
            flag = "" if abs(info["left_over"]) <= 2 else f"  left {info['left_over']}"
            print(f"  {name:<14} mode {info['mode']:#04x} stride {info['stride']} "
                  f"-> {len(out):>6} bytes{flag}")
        print(f"\n{ok} decoded, {bad} failed")
        return 0
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    data = open(sys.argv[1], "rb").read()
    out, info = decode(data)
    print(f"{sys.argv[1]}: {info}")
    if "--out" in sys.argv:
        open(sys.argv[sys.argv.index("--out") + 1], "wb").write(out)
    return 0


sys.exit(main())

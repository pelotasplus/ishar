#!/usr/bin/env python3
"""
Unpack start.exe.

Ishar ships behind an LZEXE-family self-extractor. The MZ header carries one
relocation and CS:IP = 0000:0003, at a stub that copies the whole image up by
0x0b64 paragraphs and far-jumps into the copy; the decompressor proper is the
last ~250 bytes of the image and expands the program downward into the space
the copy vacated.

This reimplements that decompressor statically, so the unpacked image is
reproducible and lands in a proper MZ EXE that chani can disassemble. It is a
transcription of the stub, not a guess at a known packer -- see stub.chani,
where every routine named in the comments here is annotated.

    tools/unpack.py [in.exe] [out.exe]

Default output is next to the game files, where --CDrive can see it.
"""
import hashlib
import os
import struct
import sys

# Image offsets, all established in stub.chani.
BITBUF = 0x003A          # first bit-stream word, read by the prologue
SRC = 0x003C             # compressed data starts here
# The relocation table is NOT in the packed file: it is compressed along with
# the program and lands at the end of the decompressed image, where the stub
# reads it as (load+0x158c):004a. Verified by reading it out of the running
# machine at the relocate breakpoint -- the same offset in the packed image
# holds compressed data.
RELOC = 0x158C * 16 + 0x4A
RELOC_COUNT = 0x8A       # the loop count at seg000:a8a9
ENTRY_IP = 0x25E5        # from the stub's final `jmp far 0000:25e5`
ENTRY_CS = 0x0000        # segment word patched with the load segment at runtime
STACK_SS = 0x158D        # `add bp,158dh / mov ss,bp`
STACK_SP = 0x0000        # `mov sp,0`


class Bits:
    """seg000:a7e3 get_bit -- 16-bit words, LSB first, refilled when the
    counter runs out. The refill does not re-shift, so the bit returned on a
    refilling call is the last bit of the old word."""

    def __init__(self, img, si):
        self.img = img
        self.si = si
        self.bp = img[BITBUF] | (img[BITBUF + 1] << 8)
        self.dl = 0x10

    def bit(self):
        cf = self.bp & 1
        self.bp >>= 1
        self.dl -= 1
        if self.dl == 0:
            self.bp = self.img[self.si] | (self.img[self.si + 1] << 8)
            self.si += 2
            self.dl = 0x10
        return cf

    def byte(self):
        b = self.img[self.si]
        self.si += 1
        return b


def unpack(raw):
    (sig, lastpg, pages, nreloc, hdrpar, _minal, _maxal,
     _ss, _sp, _ck, ip, cs, _rel, _ovl) = struct.unpack_from("<2sHHHHHHHHHHHHH", raw, 0)
    if sig != b"MZ":
        sys.exit("not an MZ executable")
    if (cs, ip) != (0x0000, 0x0003):
        sys.exit(f"entry is {cs:04x}:{ip:04x}, not 0000:0003 -- not this packer")
    hdr = hdrpar * 16
    img = raw[hdr:hdr + (pages - 1) * 512 + (lastpg or 512) - hdr]

    s = Bits(img, SRC)
    out = bytearray()

    def copy(count, bx):
        """seg000:a856 -- `mov al,es:[bx+di] / stosb / loop`. BX is a negative
        16-bit displacement, so this is a back-reference; the segment-adjust
        escape keeps it inside one segment, which is what makes it safe to
        treat DI as a flat index here."""
        off = bx - 0x10000 if bx & 0x8000 else bx
        src = len(out) + off
        if not 0 <= src < len(out):
            sys.exit(f"back-reference out of range at output {len(out):#x}: "
                     f"bx={bx:#06x} -> {src:#x}")
        for _ in range(count):
            out.append(out[src])
            src += 1

    while True:
        if s.bit():                                   # a85c: literal
            out.append(s.byte())
            continue

        short = s.bit()                               # a864
        bl = s.byte()
        bh = 0xFF

        if not short:
            if s.bit():                               # a871 -> match_long
                for _ in range(3):                    # a84b
                    bh = ((bh << 1) | s.bit()) & 0xFF
                bh = (bh - 1) & 0xFF
                copy(2, (bh << 8) | bl)               # falls into match_len2
                continue
            if bh != bl:                              # a873: not the escape
                copy(2, (bh << 8) | bl)               # match_len2
                continue
            if s.bit():                               # a87a
                # a87c: re-base ES:DI and DS:SI so DI stays inside a segment.
                # Both rebases preserve the linear address, so with flat
                # buffers there is nothing to do.
                continue
            break                                     # -> relocate

        # match_short, seg000:a7ef
        bh = ((bh << 1) | s.bit()) & 0xFF
        if not s.bit():                               # a7f7
            dh, cl = 2, 3
            while True:                               # a7fd
                if s.bit():
                    break
                bh = ((bh << 1) | s.bit()) & 0xFF
                dh = (dh << 1) & 0xFF
                cl -= 1
                if cl == 0:
                    break
            bh = (bh - dh) & 0xFF                     # a80b

        dh, cl = 2, 4                                 # a80d
        length = None
        while True:                                   # a811
            dh = (dh + 1) & 0xFF
            if s.bit():
                length = dh
                break
            cl -= 1
            if cl == 0:
                break
        if length is None:
            if s.bit():                               # a81a
                dh = (dh + 1) & 0xFF
                if s.bit():                           # a821
                    dh = (dh + 1) & 0xFF
                length = dh
            else:                                     # a82c
                if s.bit():
                    length = s.byte() + 0x11          # a841
                else:
                    dh = 0                            # a835
                    for _ in range(3):
                        dh = ((dh << 1) | s.bit()) & 0xFF
                    length = (dh + 9) & 0xFF
        copy(length, (bh << 8) | bl)

    # seg000:a8a3 relocate. Records are read from the packer's own segment at
    # offset 0x4a: a word with the high bit clear is a segment (biased by the
    # load segment at runtime, so unbiased here), followed by an offset word;
    # a word with the high bit set is a 15-bit delta on the current offset.
    if len(out) <= RELOC:
        sys.exit(f"output is {len(out):#x} bytes, too short to hold the "
                 f"relocation table at {RELOC:#x}")
    rel, si, seg, off = [], RELOC, 0, 0
    for _ in range(RELOC_COUNT):
        w = struct.unpack_from("<H", out, si)[0]
        si += 2
        if w & 0x8000:
            d = w & 0x7FFF                            # a8ba: shl/sar = 15-bit
            off = (off + (d - 0x8000 if d & 0x4000 else d)) & 0xFFFF
        else:
            seg = w                                   # unbiased; runtime adds load
            off = struct.unpack_from("<H", out, si)[0]
            si += 2
        rel.append((seg, off))
    # The table is the last thing in the image. If it is not, the record count
    # or the format is wrong and the relocations are being read off the end of
    # something else.
    if si != len(out):
        sys.exit(f"relocation table ends at {si:#x}, image ends at {len(out):#x}")
    return bytes(out), rel


def build_exe(image, rel):
    hdrlen = 0x1C + len(rel) * 4
    hdrpar = (hdrlen + 15) // 16
    hdr = hdrpar * 16
    total = hdr + len(image)
    pages = (total + 511) // 512
    h = bytearray(hdr)
    struct.pack_into("<2sHHHHHHHHHHHHH", h, 0, b"MZ", total % 512, pages, len(rel),
                     hdrpar, 0x0000, 0xFFFF, STACK_SS, STACK_SP, 0,
                     ENTRY_IP, ENTRY_CS, 0x1C, 0)
    for i, (seg, off) in enumerate(rel):
        struct.pack_into("<HH", h, 0x1C + i * 4, off, seg)
    return bytes(h) + image


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    game = os.path.join(here, "ishar_legend_of_the_fortress_DOSGamer.com")
    # The unpacked binary lives beside the game's own files, because --CDrive
    # makes that folder C: -- but it is derived, and gitignored.
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(game, "start.exe")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(game, "start-unpacked.exe")
    raw = open(src, "rb").read()
    image, rel = unpack(raw)
    exe = build_exe(image, rel)
    open(dst, "wb").write(exe)
    print(f"{src}  {len(raw)} bytes  sha1 {hashlib.sha1(raw).hexdigest()}")
    print(f"  {len(rel)} relocations rebuilt")
    print(f"{dst}  {len(exe)} bytes, image 0x{len(image):x}  "
          f"sha1 {hashlib.sha1(exe).hexdigest()}")
    print(f"  entry {ENTRY_CS:04x}:{ENTRY_IP:04x}   stack {STACK_SS:04x}:{STACK_SP:04x}")


main()

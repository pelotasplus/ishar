#!/usr/bin/env python3
"""Find a character's record by searching all of conventional memory for their stats.

T60 read BORMINH's sheet off the screen -- LEVEL 1, STRENGTH 7, CONSTITUTION 6, AGILITY 8,
INTELLIGENCE 6 -- and then failed to find those values anywhere in 64 KB of the VM's global
variable area, at any stride from 1 to 8, raw or divided by ten (FINDINGS 6.13). That was
a search of one window, not of the machine: 64 KB out of 640.

This dumps everything below the VGA aperture and looks again, for the values and for the
name, so the negative result either becomes a real one or stops being a result at all.
"""
import json, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp

st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
LO, HI = 0x00000, 0xA0000          # conventional RAM; 0xA0000 up is the framebuffer

CACHE = os.path.join(HERE, ".ish", "t68-ram.bin")

def dump():
    """640 KB over GDB takes a while, so keep it. `--fresh` retakes it."""
    if os.path.exists(CACHE) and "--fresh" not in sys.argv:
        return open(CACHE, "rb").read()
    g = Rsp(st["gdb"])
    b = bytearray()
    while LO + len(b) < HI:
        b += g.read_mem(LO + len(b), min(4096, HI - LO - len(b)))
    g.cont()
    open(CACHE, "wb").write(b)
    return bytes(b)

def strided(b, want, lo=1, hi=9, guard=None):
    """Offsets where `want` appears at a constant stride, optionally with `guard` before.

    Anchored on the first value with bytes.find, which runs in C -- scanning every offset
    in Python took longer than the run's whole budget and printed nothing, because the
    output was still sitting in the buffer when the timebox killed it.
    """
    out, first, n = [], bytes([want[0]]), len(want)
    for s in range(lo, hi):
        o = b.find(first)
        while o != -1:
            if o + n * s <= len(b) and all(b[o + i * s] == want[i] for i in range(1, n)):
                if guard is None or (o >= s and b[o - s] == guard):
                    out.append((o, s))
            o = b.find(first, o + 1)
    return out

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want = [int(x) for x in (args or "7 6 8 6".split())]
    b = dump()
    print(f"{len(b)} bytes of RAM, {LO:#07x}..{HI:#07x}")

    for name in (b"BORMINH", b"ARAMIR", b"THIEF", b"HUMAIN"):
        hits = [o for o in range(len(b) - len(name)) if b[o:o+len(name)] == name]
        print(f"  {name.decode():8s} {len(hits):3d}  "
              + ", ".join(f"{h:#07x}" for h in hits[:12]))

    print(f"\nstat values {want} as bytes:")
    for o, s in strided(b, want)[:40]:
        print(f"  {o:#07x} stride {s}   {b[o-8:o+8*s].hex(' ')}")
    print(f"\nsame, with LEVEL=1 one stride before:")
    for o, s in strided(b, want, guard=1)[:40]:
        print(f"  {o:#07x} stride {s}   ctx {b[max(0,o-16):o+8*s].hex(' ')}")

if __name__ == "__main__":
    main()

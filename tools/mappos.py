#!/usr/bin/env python3
"""Locate the resident map grid and the party's cell, from scratch.

Both are runtime addresses, so hard-coding ss:[0x644c] only works within one session.
The grid is found by probing memory for 64 bytes of each cont*.fic; the party's row and
column are the two bytes immediately after it (FINDINGS 6.7b).
"""
import json, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))

def dump(g, n=0xA0000):
    m = bytearray()
    while len(m) < n:
        m += g.read_mem(len(m), min(4096, n - len(m)))
    return bytes(m)

def find(mem):
    for i in range(1, 7):
        d = open(os.path.join(GAME, f"cont{i}.fic"), "rb").read()
        j = mem.find(d[1000:1064])
        while j >= 0:
            base = j - 1000
            if base >= 0 and mem[base:base + len(d)] == d:
                return f"cont{i}.fic", base, len(d)
            j = mem.find(d[1000:1064], j + 1)
    return None, None, None

def main():
    g = Rsp(st["gdb"])
    mem = dump(g)
    g.cont()
    name, base, n = find(mem)
    if not name:
        print("no cont*.fic resident")
        return
    end = base + n
    print(f"{name} at {base:#07x}..{end:#07x}")
    print(f"party row {mem[end]}  col {mem[end+1]}  cell {mem[base + mem[end]*90 + mem[end+1]]:#04x}")
    print(f"next 16 bytes after the grid: {mem[end:end+16].hex()}")
    print(f"as ss-relative (SS=0d88): {end - 0x0d880:#06x}")

main()

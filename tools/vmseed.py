#!/usr/bin/env python3
"""
Find every jump table in the image and seed its targets as code.

The VM's dispatch (`2e ff a5 f2 01` -- jmp cs:[di+01f2]) is not the only one:
the same shape appears wherever the game switches on a byte. Each table is a run
of words pointing into the segment that reads it, so once the instruction is
found the table can be walked until the words stop being plausible code.

    tools/vmseed.py            # report what it finds
    tools/vmseed.py --write    # append the seeds to ishar.chani
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDR = 0x250
IMG = open(os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com",
                        "start-unpacked.exe"), "rb").read()
# (name, image start, image end) -- from tools/segmap.py
SEGS = [("seg_0000", 0x00000, 0x09410), ("seg_0941", 0x09410, 0x0e970),
        ("seg_0e97", 0x0e970, 0x13d70), ("seg_13d7", 0x13d70, 0x15a00)]


def seg_of(rel):
    for name, a, b in SEGS:
        if a <= rel < b:
            return name, a
    return None, None


def body(name):
    for n, a, b in SEGS:
        if n == name:
            return a, b
    return None, None


# jmp cs:[di+imm16] / jmp cs:[bx+imm16] / jmp cs:[si+imm16], with and without 2E
PATTERNS = [(b"\x2e\xff\xa5", 5), (b"\x2e\xff\xa7", 5), (b"\x2e\xff\xa4", 5),
            (b"\xff\xa5", 4), (b"\xff\xa7", 4), (b"\xff\xa4", 4)]

tables = {}
for pat, ilen in PATTERNS:
    start = 0
    while True:
        i = IMG.find(pat, start)
        if i < 0:
            break
        start = i + 1
        rel = i - HDR
        sname, sbase = seg_of(rel)
        if sname is None:
            continue
        disp = struct.unpack_from("<H", IMG, i + len(pat))[0]
        lo, hi = body(sname)
        # walk the table while the words look like offsets inside this segment
        # A table may open with zero entries (029c starts with three), so tolerate
        # gaps and stop only after a run of entries that cannot be code.
        n, targets, miss = 0, [], 0
        while n < 512 and miss < 4:
            o = HDR + lo + disp + n * 2
            if o + 2 > len(IMG):
                break
            w = struct.unpack_from("<H", IMG, o)[0]
            if 0x100 <= w <= (hi - lo):
                targets.append(w)
                miss = 0
            else:
                miss = miss + 1 if w != 0 else miss
            n += 1
        if len(targets) >= 8:
            key = (sname, disp)
            if key not in tables or len(targets) > len(tables[key][1]):
                tables[key] = (rel - sbase, sorted(set(targets)))

total = 0
seeds = []
for (sname, disp), (site, targets) in sorted(tables.items()):
    print(f"{sname}: dispatch at {site:#06x} -> table {disp:#06x}, "
          f"{len(targets)} distinct targets "
          f"{min(targets):#06x}..{max(targets):#06x}")
    total += len(targets)
    for t in targets:
        seeds.append((sname, t, disp))
print(f"\n{len(tables)} tables, {total} target addresses "
      f"({len({(s, t) for s, t, _ in seeds})} distinct)")

if "--write" in sys.argv:
    c = open(os.path.join(HERE, "ishar.chani")).read().rstrip()
    assert c.endswith("end")
    have = set(re.findall(r"attr\[(seg_\w+):([0-9a-f]{4})\]", c))
    lines = ["", "// Jump-table targets, found by tools/vmseed.py (T26). Every "
             "`jmp cs:[reg+imm]`", "// in the image names a table; its entries are "
             "code by construction."]
    added = 0
    for sname, t, disp in sorted(set(seeds)):
        if (sname, f"{t:04x}") in have:
            continue
        have.add((sname, f"{t:04x}"))
        lines.append(f"attr[{sname}:{t:04x}]: type = code; "
                     f"name = disp_{disp:04x}_{t:04x}")
        added += 1
    open(os.path.join(HERE, "ishar.chani"), "w").write(
        c[:-3].rstrip() + "\n" + "\n".join(lines) + "\nend\n")
    print(f"appended {added} new seeds to ishar.chani")

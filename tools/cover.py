#!/usr/bin/env python3
"""
Coverage of the listing: how much of the code segments decoded as instructions
rather than `db`.

Split out of disasm.sh because it has to fail loudly. An earlier version was a
grep pipeline that matched nothing after the listing failed to build, divided
0 by 0 and printed "coverage 100.0%" -- which is exactly the kind of number
this project must never produce.
"""
import collections, os, re, sys

def code_bytes():
    """Total size of the code segments, read out of ishar.chani.

    Derived, not hardcoded: this was 0x12ed0..0x1b730 while the unpacker was
    dropping 64 KB of the image, and a stale constant reported -187.7% coverage
    rather than saying the map had moved.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    text = open(os.path.join(here, "ishar.chani")).read()
    total = 0
    for m in re.finditer(r"segment\[(seg_\w+)\]:.*?"
                         r"load\s*=\s*\[0\.\.\]:exe\[0x([0-9a-f]+)\.\.0x([0-9a-f]+)\]",
                         text, re.S):
        total += int(m.group(3), 16) - int(m.group(2), 16)
    if not total:
        sys.exit("cover: no code segments in ishar.chani")
    return total


path = sys.argv[1] if len(sys.argv) > 1 else "ishar-listing.txt"
line = re.compile(r"^(seg_[0-9a-f]{4}):([0-9a-f]+)\s{6,}(\S+)")
seen, undecoded = collections.Counter(), collections.Counter()
for ln in open(path):
    m = line.match(ln)
    if m:
        seen[m.group(1)] += 1
        if m.group(3) in ("db", "dw", "dd"):
            undecoded[m.group(1)] += 1

if not seen:
    sys.exit(f"cover: {path} has no code lines -- did the disassembler fail?")

# A listing older than the database is a listing that describes a different
# database. disasm.sh aborts when the parse fails, but nothing stopped this
# script from being run on its own and reporting off whatever was left on disk
# -- which is how three .chani edits in a row all printed an unchanged 12.0%
# while ishar.chani did not parse at all. Empty was already an error; stale
# has to be one too.
if os.path.getmtime(path) < os.path.getmtime("ishar.chani"):
    sys.exit(f"cover: {path} is older than ishar.chani -- "
             f"rerun tools/disasm.sh; the number would describe the old database")

total = code_bytes()
db = sum(undecoded.values())
print(f"  instructions {sum(seen.values()) - db:6}   undecoded {db:6} bytes"
      f"   coverage {100 * (total - db) / total:.1f}%")
for s in sorted(seen):
    print(f"    {s}  decoded {seen[s] - undecoded[s]:6}   db {undecoded[s]:6}")

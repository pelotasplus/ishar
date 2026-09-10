#!/usr/bin/env python3
"""
Does the FORMATS.md-only decoder reproduce what the game actually put on screen?

Dumps the live 320x200 framebuffer at 0xA0000 and searches every asset decoded by
java/IsharCorpus for that exact run of bytes. A hit is not "looks plausible": it is
the decoder having predicted the pixels the game blitted, byte for byte.
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp

st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
g = Rsp(st["gdb"])
fb = bytearray()
for i in range(0, 64000, 4000):
    fb += g.read_mem(0xA0000 + i, 4000)
fb = bytes(fb)
open(os.path.join(HERE, ".ish", "fb.bin"), "wb").write(fb)

nonzero = len(set(fb))
print(f"framebuffer: {len(fb)} bytes, {nonzero} distinct values")
if nonzero < 3:
    sys.exit("screen is blank -- nothing to match against")

# match on a distinctive middle row, then confirm the whole image from there
row = fb[100 * 320:101 * 320]
out = os.path.join(HERE, "java", "out")
hits = []
for n in sorted(os.listdir(out)):
    if not n.endswith(".bin"):
        continue
    data = open(os.path.join(out, n), "rb").read()
    i = data.find(row)
    if i < 0:
        continue
    start = i - 100 * 320
    if start < 0 or start + 64000 > len(data):
        hits.append((n, i, "row only"))
        continue
    full = data[start:start + 64000]
    same = sum(1 for a, b in zip(full, fb) if a == b)
    hits.append((n, start, f"{same}/64000 = {100*same/64000:.2f}%"))

if not hits:
    print("NO asset contains the screen's row 100")
for n, o, w in hits:
    print(f"  {n}  at offset {o}  {w}")

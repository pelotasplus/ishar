#!/usr/bin/env python3
"""Walk a line and capture the viewport at each cell, labelled by the cell's grid value.

If the low cell values are per-cell scenery markers (FINDINGS 6.7), two cells sharing a
value should show the same object. This produces the pairs to compare.
"""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import png, urllib.request
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})
GRID = open(os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com",
                        "cont1.fic"), "rb").read()
ROW = 0x644c

def read(g, base):
    b = g.read_mem(base + ROW, 2)
    v = bytearray()
    while len(v) < 64000:
        v += g.read_mem(0xa0000 + len(v), min(4096, 64000 - len(v)))
    pal = bytes.fromhex(mcp("read_memory", {"segment": 0, "offset": 0, "length": 1})["Data"]) \
        if False else None
    g.cont()
    return (b[0], b[1]), bytes(v)

def main():
    key = sys.argv[1]
    n = int(sys.argv[2])
    outdir = os.path.join(HERE, os.environ.get("LOOKDIR", "captures/t11g3"))
    os.makedirs(outdir, exist_ok=True)
    base = mcp("read_cpu_state")["SS"] * 16
    g = Rsp(st["gdb"])
    seen = []
    for i in range(n):
        (r, c), v = read(g, base)
        val = GRID[r * 90 + c]
        # viewport only: rows 0..118, cols 0..319 is the 3D view area
        rows = [[(v[y*320+x],)*3 for x in range(320)] for y in range(0, 118)]
        f = os.path.join(outdir, f"cell-{val:02x}-r{r}c{c}.png")
        png.write(f, rows)
        seen.append((val, r, c, f))
        print(f"  ({r},{c}) value {val:#04x} -> {os.path.basename(f)}")
        subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", key], capture_output=True)
        time.sleep(1.1)
    vals = {}
    for val, r, c, f in seen:
        vals.setdefault(val, []).append((r, c))
    print("\nvalues seen:", {hex(k): v for k, v in sorted(vals.items())})

main()

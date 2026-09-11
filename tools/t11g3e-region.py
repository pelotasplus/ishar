#!/usr/bin/env python3
"""Find the byte that holds the region id.

The panel's region name changes from DRAGONIA to ANGARAHN while the same cont1.fic stays
resident, so the name is not the grid file. Sample DGROUP at several cells on each side and
keep the bytes that are constant within a region and different between them.
"""
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})

def snap(g, base):
    b = bytearray()
    while len(b) < 0x10000:
        b += g.read_mem(base + len(b), min(4096, 0x10000 - len(b)))
    g.cont()
    return bytes(b)

def main():
    groups = []          # [(label, [(r,c), ...])]
    for arg in sys.argv[1:]:
        label, cells = arg.split("=")
        groups.append((label, [tuple(int(x) for x in p.split(",")) for p in cells.split(";")]))
    base = mcp("read_cpu_state")["SS"] * 16
    g = Rsp(st["gdb"])
    samples = {}
    for label, cells in groups:
        samples[label] = []
        for r, c in cells:
            subprocess.run([sys.executable, os.path.join(HERE, "tools", "walkto.py"),
                            str(r), str(c)], capture_output=True)
            samples[label].append(snap(g, base))
            print(f"  sampled {label} at ({r},{c})")
    labels = [l for l, _ in groups]
    hits = []
    for o in range(0x10000):
        vals = {l: {s[o] for s in samples[l]} for l in labels}
        if any(len(v) != 1 for v in vals.values()):
            continue
        got = [next(iter(vals[l])) for l in labels]
        if len(set(got)) == len(labels):
            hits.append((o, got))
    print(f"\n{len(hits)} bytes constant within each region and different between:")
    for o, got in hits[:40]:
        print(f"  ss:[{o:04x}] {got}")

main()

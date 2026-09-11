#!/usr/bin/env python3
"""Find the party's map coordinates by moving it and diffing DGROUP.

The party walks a 90x54 grid (FORMATS 3.12). A forward step must change some small
integer by one, so: snapshot DGROUP, step, snapshot, and keep the words that moved by
exactly +-1 and stay inside the grid. Repeated steps in one direction narrow it to a
monotone run, which a counter or a timer cannot fake.
"""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import urllib.request

st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})

def snap(g, base, n=0x10000):
    b = bytearray()
    while len(b) < n:
        b += g.read_mem(base + len(b), min(4096, n - len(b)))
    v = bytearray()
    while len(v) < 64000:                 # the viewport is the proof a step happened
        v += g.read_mem(0xa0000 + len(v), min(4096, 64000 - len(v)))
    g.cont()
    return bytes(b), bytes(v)

def w(buf, o):
    return buf[o] | (buf[o+1] << 8)

def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "Up"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    cpu = mcp("read_cpu_state")
    base = cpu["SS"] * 16
    print(f"SS={cpu['SS']:04x}  DGROUP at {base:#07x}")
    g = Rsp(st["gdb"])
    snaps, vrams = [], []
    d, v = snap(g, base); snaps.append(d); vrams.append(v)
    for i in range(steps):
        subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", key],
                       capture_output=True)
        time.sleep(1.2)
        d, v = snap(g, base); snaps.append(d); vrams.append(v)
        ch = sum(1 for a, b in zip(vrams[-2], vrams[-1]) if a != b) * 100.0 / 64000
        dd = sum(1 for a, b in zip(snaps[-2], snaps[-1]) if a != b)
        print(f"  step {i+1} {key}: screen {ch:5.1f}% changed, {dd} DGROUP bytes moved")
    out = os.path.join(HERE, ".ish", f"t11g3-{key}.json")
    json.dump([s.hex() for s in snaps], open(out, "w"))
    # any CONSTANT non-zero step is a candidate: a move need not be one grid unit,
    # and the first run found nothing because it demanded exactly +-1.
    cands = []
    for o in range(0, 0x10000 - 1):
        vs = [w(s, o) for s in snaps]
        d = [vs[i+1] - vs[i] for i in range(len(vs) - 1)]
        if d[0] and len(set(d)) == 1 and abs(d[0]) < 4096:
            cands.append((o, vs, d[0]))
    print(f"{len(cands)} words move by a constant non-zero step; snapshots -> {out}")
    for o, vs, step in sorted(cands, key=lambda c: abs(c[2]))[:40]:
        print(f"  ss:[{o:04x}] step {step:+6d}  {vs}")

main()

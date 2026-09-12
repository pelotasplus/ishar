#!/usr/bin/env python3
"""Dump the drawable-instance pool: each object's own viewport X and Y.

An instance persists across frames, which is what the row-step capture lacks -- there, a
sprite cannot be told from another of the same kind. FORMATS 3.17: 38 bytes each, allocated
from the pool at ss:[0be8], linked through +4, with X at +0x0c and Y at +0x0e.

    tools/t54c-instances.py [count]
"""
import json, os, struct, sys, urllib.request
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
            j = json.loads(ln[5:])["result"]
            return j.get("structuredContent", j)
SIZE = 38

def main():
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    ss = mcp("read_cpu_state")["SS"]
    def rd(seg, off, n):
        return bytes.fromhex(mcp("read_memory",
                                 {"segment": seg, "offset": off, "length": n})["Data"])
    p = rd(ss, 0x0be8, 4)
    base = int.from_bytes(p[2:], "little") * 16 + int.from_bytes(p[:2], "little")
    free = int.from_bytes(rd(ss, 0x0bec, 2), "little")
    pos = rd(ss, 0x644c, 2)
    print(f"pool at {base:#07x}, free head {free:#06x} ({free // SIZE} records), "
          f"party ({pos[0]},{pos[1]})")
    g = Rsp(st["gdb"])
    mem = bytearray()
    n = min(free + SIZE, 0x4000)
    while len(mem) < n:
        mem += g.read_mem(base + len(mem), min(4096, n - len(mem)))
    g.cont()
    print(f"  {'off':>6} {'flags':>5} {'op':>3} {'next':>6} {'ptr':>6} "
          f"{'X':>5} {'Y':>5} {'+16':>6} {'x2':>5} {'y2':>5}")
    # Instances are NOT packed from offset 0 -- the chain in FORMATS 3.17 runs 0x74 -> 0x9a,
    # 38 apart but not from zero. So scan every offset for the structural signature: the
    # 0x7fff bounding-box sentinel at +16, with an on-screen X,Y at +0x0c.
    shown = 0
    for off in range(0, len(mem) - SIZE, 2):
        r = mem[off:off + SIZE]
        x, y = struct.unpack_from("<hh", r, 0x0c)
        if struct.unpack_from("<H", r, 16)[0] != 0x7fff:
            continue
        if not (0 <= x < 320 and 0 <= y < 200):
            continue
        nxt, ptr = struct.unpack_from("<HH", r, 4)[0], struct.unpack_from("<H", r, 6)[0]
        s16 = struct.unpack_from("<H", r, 16)[0]
        x2, y2 = struct.unpack_from("<hh", r, 22)
        print(f"  {off:6} {r[0]:#05x} {r[1]:3} {nxt:6} {ptr:6} "
              f"{x:5} {y:5} {s16:#07x} {x2:5} {y2:5}")
        shown += 1
        if shown >= want:
            break
    print(f"  {shown} records with an on-screen X,Y")

main()

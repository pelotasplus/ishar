#!/usr/bin/env python3
"""Sample the region caption over a lattice of cells to map the regions.

The caption is not in the cell value -- FRAGONIR and ANGARAHN meet between columns 45 and
46 with 0x00 on both sides -- so the region must come from the coordinates. This walks to
each sample cell and reads the caption there.

Avoid cells near (14,57): stepping north there bounces the party back to the start.
"""
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})
NAMES = {b"FRAGONIR", b"ANGARAHN", b"OSGHIROD", b"LOTHARIA", b"RHUDGAST", b"FIMNUIRH",
         b"ARAGARTH", b"KANDOMIR", b"SILMATIL", b"URSHURAK", b"BALDARON", b"VARGAEON",
         b"ZENDORIA", b"GIL-ARAS", b"HALINDOR", b"ULDONYAR", b"VALATHAR", b"ELWINGIL",
         b"FHULGROD", b"  ISHAR ", b"L'OCEAN "}

def caption(ss):
    """Only trust a read that spells one of the 21 names -- the buffer is shared."""
    for _ in range(6):
        b = bytes.fromhex(mcp("read_memory",
                              {"segment": ss, "offset": 0x0902, "length": 8})["Data"])
        if b in NAMES:
            return b.decode().strip()
        time.sleep(0.4)
    return None

def pos(ss):
    d = bytes.fromhex(mcp("read_memory", {"segment": ss, "offset": 0x644c, "length": 2})["Data"])
    return d[0], d[1]

def main():
    cells = [tuple(int(x) for x in a.split(",")) for a in sys.argv[1:]]
    ss = mcp("read_cpu_state")["SS"]
    out = []
    for r, c in cells:
        subprocess.run([sys.executable, os.path.join(HERE, "tools", "walkto.py"),
                        str(r), str(c)], capture_output=True)
        here = pos(ss)
        nm = caption(ss)
        out.append((here, nm))
        print(f"  ({here[0]:2},{here[1]:2}) {nm}", flush=True)
    print("\nsummary:")
    for (r, c), nm in out:
        print(f"  row {r:2} col {c:2} -> {nm}")

main()

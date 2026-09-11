#!/usr/bin/env python3
"""Read the region caption and the bytes around the party's position record.

The caption lands in a DGROUP buffer at ss:[0x0902] (FINDINGS 4.19b), so the region the
game thinks the party is in is readable without a screenshot. That makes it cheap to walk
a transect and record where the name changes.
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
NAME, ROW = 0x0902, 0x644c
GRID = open(os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com",
                        "cont1.fic"), "rb").read()

def read(ss, off, n):
    return bytes.fromhex(mcp("read_memory", {"segment": ss, "offset": off, "length": n})["Data"])

def state(ss):
    p = read(ss, ROW, 2)
    nm = read(ss, NAME, 8).decode("latin1").strip()
    return (p[0], p[1]), nm

def main():
    ss = mcp("read_cpu_state")["SS"]
    if sys.argv[1] == "here":
        (r, c), nm = state(ss)
        print(f"({r},{c}) cell {GRID[r*90+c]:#04x}  region {nm!r}")
        print("  32 bytes at the position record:", read(ss, ROW, 32).hex())
        return
    # transect: walk cell by cell in one direction, reading the caption each step
    key, n = sys.argv[1], int(sys.argv[2])
    out = []
    for _ in range(n):
        (r, c), nm = state(ss)
        out.append((r, c, GRID[r*90+c], nm))
        subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", key], capture_output=True)
        time.sleep(0.85)
    prev = None
    for r, c, v, nm in out:
        mark = "  <-- region change" if prev and nm != prev else ""
        print(f"  ({r:2},{c:2}) cell {v:#04x}  {nm}{mark}")
        prev = nm

main()

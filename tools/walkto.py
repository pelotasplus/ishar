#!/usr/bin/env python3
"""Walk the party to a map cell, reading its position after every step.

Greedy with a blocked set learned as it goes: a move that leaves the position unchanged
marks that cell blocked and the route is replanned. Beats hand-driving 30 steps, and the
position readout is the only way to know a step landed.
"""
import json, os, subprocess, sys, time, urllib.request
from collections import deque
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
GRID = open(os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com",
                        "cont1.fic"), "rb").read()
ROW = 0x644c
DIRS = {"Up": (1, 0), "Down": (-1, 0), "Right": (0, 1), "Left": (0, -1)}
# Everything at or above 0x40 is area terrain or a building and has never been walked
# on; 0x0a is the one low value observed to refuse a move (FINDINGS 6.7b). Blocked cells
# learned at runtime are added on top of this.
def blocked(v):
    return v >= 0x40 or v == 0x0a

def cell(r, c):
    return GRID[r * 90 + c] if 0 <= r < 54 and 0 <= c < 90 else 0xCD


def route(a, b, bad):
    prev = {a: None}
    q = deque([a])
    while q:
        p = q.popleft()
        if p == b:
            out = []
            while prev[p]:
                out.append(prev[p][1]); p = prev[p][0]
            return out[::-1]
        for k, (dr, dc) in DIRS.items():
            n = (p[0] + dr, p[1] + dc)
            if n in prev or n in bad or blocked(cell(*n)):
                continue
            prev[n] = (p, k); q.append(n)
    return None

def main():
    tr, tc = int(sys.argv[1]), int(sys.argv[2])
    ss = mcp("read_cpu_state")["SS"]
    def pos():
        d = mcp("read_memory", {"segment": ss, "offset": ROW, "length": 2})["Data"]
        return (int(d[:2], 16), int(d[2:], 16))
    bad, here = set(), pos()
    print(f"start {here} -> ({tr},{tc})")
    for _ in range(200):
        if here == (tr, tc):
            print(f"arrived at {here}, cell {cell(*here):#04x}")
            return
        r = route(here, (tr, tc), bad)
        if not r:
            print(f"no route from {here}; {len(bad)} cells learned blocked")
            return
        k = r[0]
        subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", k], capture_output=True)
        time.sleep(0.85)
        now = pos()
        if now == here:
            dr, dc = DIRS[k]
            bad.add((here[0] + dr, here[1] + dc))
            print(f"  {k} refused at {here}; cell {cell(here[0]+dr, here[1]+dc):#04x} blocked")
        here = now
    print(f"gave up at {here}")

main()

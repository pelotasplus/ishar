#!/usr/bin/env python3
"""Probe which neighbours the party can walk into, and what the grid says about them.

The party's cell is ss:[644c] (row) / ss:[644d] (col) -- established by driving Up/Down
and Left/Right and watching which byte moves. A move that leaves the pair unchanged was
refused, so the cell it aimed at is blocked. Pairing refusals with cell values is what
turns the grid from a picture into terrain.
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

ROW, COL = 0x644c, 0x644d
DIRS = {"Up": (1, 0), "Down": (-1, 0), "Right": (0, 1), "Left": (0, -1)}
GRID = open(os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com",
                        "cont1.fic"), "rb").read()

def pos(g, base):
    b = g.read_mem(base + ROW, 2)
    g.cont()
    return b[0], b[1]

def cell(r, c):
    return GRID[r * 90 + c] if 0 <= r < 54 and 0 <= c < 90 else None

def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    base = mcp("read_cpu_state")["SS"] * 16
    g = Rsp(st["gdb"])
    blocked, opened = {}, {}
    order = list(DIRS)
    for i in range(rounds):
        here = pos(g, base)
        for k in order:
            subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", k], capture_output=True)
            time.sleep(1.0)
            now = pos(g, base)
            dr, dc = DIRS[k]
            tgt = (here[0] + dr, here[1] + dc)
            v = cell(*tgt)
            if now == here:
                blocked[tgt] = v
            else:
                opened[now] = cell(*now)
                # step back so the sweep stays put
                back = {"Up": "Down", "Down": "Up", "Left": "Right", "Right": "Left"}[k]
                subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", back],
                               capture_output=True)
                time.sleep(1.0)
                here = pos(g, base)
        # wander one cell so the next round samples somewhere new
        for k in ("Up", "Right", "Down", "Left"):
            subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", k], capture_output=True)
            time.sleep(1.0)
            if pos(g, base) != here:
                break
        print(f"  round {i+1}: at {pos(g, base)}, {len(blocked)} blocked / {len(opened)} open so far")
    bv = sorted(set(v for v in blocked.values() if v is not None))
    ov = sorted(set(v for v in opened.values() if v is not None))
    print(f"\nblocked cells ({len(blocked)}): values {[hex(v) for v in bv]}")
    print(f"open cells    ({len(opened)}): values {[hex(v) for v in ov]}")
    print(f"values that are ONLY blocked: {[hex(v) for v in bv if v not in ov]}")
    print(f"values that are ONLY open:    {[hex(v) for v in ov if v not in bv]}")
    json.dump({"blocked": {f"{r},{c}": v for (r, c), v in blocked.items()},
               "open": {f"{r},{c}": v for (r, c), v in opened.items()}},
              open(os.path.join(HERE, ".ish", "t11g3-walk.json"), "w"), indent=1)

main()

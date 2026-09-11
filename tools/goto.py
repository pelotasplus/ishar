#!/usr/bin/env python3
"""Put the party on a given map cell by writing its row/col, then force a redraw.

The party's cell is the two bytes right after the resident grid (FINDINGS 6.7b), so
walking to a far corner of a 90x54 world is unnecessary: write the pair and step once.
Teleporting into an impassable cell is avoided by aiming at a walkable neighbour.

    tools/goto.py <row> <col> [name]        -> captures/<name>.png
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
ROW, COL = 0x644c, 0x644d
GRID = open(os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com",
                        "cont1.fic"), "rb").read()

def main():
    r, c = int(sys.argv[1]), int(sys.argv[2])
    name = sys.argv[3] if len(sys.argv) > 3 else f"goto-r{r}c{c}"
    ss = mcp("read_cpu_state")["SS"]
    mcp("write_memory", {"segment": ss, "offset": ROW, "data": f"{r:02x}{c:02x}"})
    cur = mcp("read_memory", {"segment": ss, "offset": ROW, "length": 2})["Data"]
    print(f"wrote ({r},{c}); reads back {cur}; cell value {GRID[r*90+c]:#04x}")
    # a step and a step back forces the view to rebuild without moving the party
    for k in ("Up", "Down"):
        subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", k], capture_output=True)
        time.sleep(1.1)
    now = mcp("read_memory", {"segment": ss, "offset": ROW, "length": 2})["Data"]
    print(f"after the nudge the party is at {now}")
    subprocess.run([os.path.join(HERE, "tools", "ish"), "shot", name], capture_output=True)
    print(f"captures/{name}.png")

main()

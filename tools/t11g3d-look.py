#!/usr/bin/env python3
"""Capture the viewport along a walk, labelled by the value of the cell AHEAD.

Which cell a value describes matters: standing on a marker is not the same as looking at
it. The party's facing is constant along a straight walk, so the cell one step ahead in the
walking direction is what fills the view -- that is the label.

Two cells with the same value should give the same object; two with different values
should not. Comparison is by hand, at 1:1 -- never downscaled (CLAUDE.md).
"""
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import png
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
DIRS = {"Up": (1, 0), "Down": (-1, 0), "Right": (0, 1), "Left": (0, -1)}
VIEW = (0, 0, 500, 250)          # the 3D viewport inside the 640x400 screenshot

def cell(r, c):
    return GRID[r * 90 + c] if 0 <= r < 54 and 0 <= c < 90 else None

def crop(src, dst):
    w, h, rows = png.read(src)
    x0, y0, x1, y1 = VIEW
    png.write(dst, [row[x0 * 3:x1 * 3] if isinstance(row[0], int) else row[x0:x1]
                    for row in rows[y0:y1]])

def main():
    key, n = sys.argv[1], int(sys.argv[2])
    out = os.path.join(HERE, "captures", "t11g3d")
    os.makedirs(out, exist_ok=True)
    ss = mcp("read_cpu_state")["SS"]
    dr, dc = DIRS[key]
    seen = []
    for _ in range(n):
        p = bytes.fromhex(mcp("read_memory", {"segment": ss, "offset": 0x644c, "length": 2})["Data"])
        r, c = p[0], p[1]
        ahead = cell(r + dr, c + dc)
        if ahead is None:
            break
        tmp = f"t11g3d-tmp"
        subprocess.run([os.path.join(HERE, "tools", "ish"), "shot", tmp], capture_output=True)
        dst = os.path.join(out, f"ahead-{ahead:02x}-from-r{r}c{c}-{key}.png")
        crop(os.path.join(HERE, "captures", tmp + ".png"), dst)
        seen.append((ahead, r, c))
        print(f"  at ({r:2},{c:2}) facing {key}: ahead is {ahead:#04x} -> {os.path.basename(dst)}",
              flush=True)
        subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", key], capture_output=True)
        time.sleep(0.9)
    from collections import Counter
    print("\nvalues captured:", Counter(v for v, _, _ in seen).most_common())

main()

#!/usr/bin/env python3
"""Watch a few DGROUP bytes while driving the party. Prints one row per key sent."""
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

OFFS = [0x644c, 0x644d, 0x8716, 0x9457, 0x9962, 0x99f7,
        0x9c28, 0x9c29, 0x9cc6, 0x9dfa, 0x9e9a, 0x90a0, 0x97dc]

def read(g, base):
    lo, hi = min(OFFS), max(OFFS) + 1
    b = bytearray()
    while len(b) < hi - lo:
        b += g.read_mem(base + lo + len(b), min(4096, hi - lo - len(b)))
    g.cont()
    return {o: b[o - lo] for o in OFFS}

def main():
    keys = sys.argv[1:] or ["Up"]
    base = mcp("read_cpu_state")["SS"] * 16
    g = Rsp(st["gdb"])
    hdr = "key        " + " ".join(f"{o:04x}" for o in OFFS)
    print(hdr)
    v = read(g, base)
    print("start      " + " ".join(f"{v[o]:4d}" for o in OFFS))
    for k in keys:
        subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", k], capture_output=True)
        time.sleep(1.2)
        v = read(g, base)
        print(f"{k:<10} " + " ".join(f"{v[o]:4d}" for o in OFFS))

main()

#!/usr/bin/env python3
"""Which script reads the map grid?

The only genuine consumer of a map cell is inside the VM expression evaluator, so the
cell is read by bytecode. At each MEMORY_READ stop, DS:SI is the script's program counter,
and matching 64 bytes there against every decoded asset names the script.
"""
import json, os, subprocess, sys, time, urllib.request
from collections import Counter
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
_ns = {}
exec(open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0], _ns)
decode = _ns["decode"]
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
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

assets = {}
for n in sorted(os.listdir(GAME)):
    if n.lower().endswith(".io"):
        try: assets[n] = decode(open(os.path.join(GAME, n), "rb").read())[0]
        except Exception: pass

def main():
    r0, c0, key = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    addr = 0x129d0 + r0 * 90 + c0
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "MEMORY_READ", "condition": None})
    g = Rsp(st["gdb"])
    for _ in range(3):
        subprocess.Popen([os.path.join(HERE, "tools", "ish"), "keys", key])
    who, sites, t0 = Counter(), Counter(), time.time()
    while time.time() - t0 < 40 and sum(sites.values()) < 20:
        g.cont()
        if g.wait_stop(timeout=40 - (time.time() - t0)) is None:
            break
        reg = g.registers()
        rel = reg["ip"] - load * 16
        # seg_0000:3d64 is wait_loop -- where the machine sits when idle. Any MCP call or
        # UI pause pushes a stop from there, and it is not a read of the watched cell
        # (CLAUDE.md, "any pause reaches the GDB client"). Count it, never believe it.
        if rel == 0x3d64:
            sites["phantom"] += 1
            continue
        sites[rel] += 1
        ds, si = reg["ds"], reg["si"] & 0xffff
        try:
            raw = g.read_mem(ds * 16 + si, 64)
        except Exception:
            continue
        cands = [n for n, d in assets.items()
                 if d.find(raw) >= 0 and d.find(raw, d.find(raw) + 1) < 0]
        who[cands[0] if len(cands) == 1 else "?"] += 1
    mcp("clear_breakpoints"); g.cont()
    print(f"cell ({r0},{c0}) at {addr:#07x}: {sum(sites.values())} reads")
    print("  sites:", {(k if isinstance(k, str) else f"seg_0000:{k:04x}"): v for k, v in sites.most_common(6)})
    print("  scripts at DS:SI:", who.most_common(6))

main()

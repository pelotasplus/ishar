#!/usr/bin/env python3
"""Who reads a map cell, and what do they do with the value?

Comparing viewports labelled by the cell ahead was confounded -- the view holds many cells
at once, so two cells with the same value gave different pictures. The reliable route is
the consumer: arm a MEMORY_READ on one cell, walk, and see which code touches it.

A memory breakpoint's IP is not the armed address, so the check is different from an
execution breakpoint's: the instruction at the reported CS:IP has to be one that reads
memory, and the cycle count must not have moved between the stop and the read (CLAUDE.md).
"""
import json, os, subprocess, sys, time, urllib.request
from collections import Counter
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

def main():
    r0, c0 = int(sys.argv[1]), int(sys.argv[2])
    key = sys.argv[3] if len(sys.argv) > 3 else "Right"
    base = 0x129d0
    addr = base + r0 * 90 + c0
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "MEMORY_READ", "condition": None})
    print(f"watching cell ({r0},{c0}) at {addr:#07x}; load {load:04x}")
    g = Rsp(st["gdb"])
    subprocess.Popen([os.path.join(HERE, "tools", "ish"), "keys", key])
    sites = Counter()
    t0 = time.time()
    while time.time() - t0 < 30 and sum(sites.values()) < 25:
        g.cont()
        if g.wait_stop(timeout=30 - (time.time() - t0)) is None:
            break
        reg = g.registers()
        cs, ip = reg["cs"], reg["ip"]
        sites[(cs, ip)] += 1
    mcp("clear_breakpoints")
    g.cont()
    print(f"{sum(sites.values())} stops at {len(sites)} distinct sites:")
    for (cs, ip), n in sites.most_common(12):
        rel = ip - load * 16
        print(f"  cs={cs:04x} ip={ip:#07x}  listing seg_0000:{rel:04x}  x{n}")

main()

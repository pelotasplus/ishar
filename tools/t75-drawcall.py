#!/usr/bin/env python3
"""Read statement 0x49's operands at the moment it runs, to see what a map cell selects.

A scene script's switch on a map cell ends in statement `0x49`, whose handler
(`seg_0000:336f`) evaluates four expressions into `ss:[0c02]`, `ss:[0c04]`, `ss:[0c06]`
and `ss:[0c0e]`, then enters `loc_seg_0000_03415` (FINDINGS 4.19f). The fourth is an index:
`seg_0000:39fd` does `base + 4*index` out of the running asset's own directory.

Breaking at `seg_0000:33a0` -- the jump at the end of the handler, after all four
evaluations -- is the only place all four are populated at once.
"""
import json, os, struct, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import urllib.request

OFF = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x33a0
SECS = int(sys.argv[2]) if len(sys.argv) > 2 else 40
WANT = int(sys.argv[3]) if len(sys.argv) > 3 else 12
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))

def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:])
            return j.get("result", {}).get("structuredContent", j)

def main():
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    cpu = mcp("read_cpu_state")
    ss = cpu["SS"] * 16
    g = Rsp(st["gdb"])
    entry = load * 16 + OFF
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS",
                           "condition": None})
    gb = g.read_mem(ss + 0x0bf6, 4)
    gbase = ((gb[3] << 8 | gb[2]) * 16) + (gb[1] << 8 | gb[0])
    print(f"break seg_0000:{OFF:04x} = {entry:#07x}   SS={cpu['SS']:04x}  "
          f"globals={gbase:#07x}")
    print("  hit  0c02  0c04  0c06  0c0e  0c12   party    cell")
    hits, t0 = 0, time.time()
    while time.time() - t0 < SECS and hits < WANT:
        g.cont()
        if g.wait_stop(timeout=max(1, SECS - (time.time() - t0))) is None:
            break
        r = g.registers()
        if r["ip"] != entry:                 # any pause reaches the client (T27b)
            continue
        hits += 1
        v = g.read_mem(ss + 0x0c02, 0x14)
        w = lambda o: struct.unpack_from("<H", v, o)[0]
        p = g.read_mem(gbase + 0x137c, 3)
        cell = g.read_mem(gbase + 0x0080 + p[0] * 90 + p[1], 1)[0]
        print(f"  {hits:3d}  {w(0):5d} {w(2):5d} {w(4):5d} {w(0x0c):5d} "
              f"{v[0x10]:5d}   ({p[0]:2d},{p[1]:2d})  {cell:#04x}")
    mcp("clear_breakpoints")
    g.cont()

if __name__ == "__main__":
    main()

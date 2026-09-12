#!/usr/bin/env python3
"""Where in a script's bytecode is the map read?

Widens t11g3d-who.py: drives the party back and forth across a watched cell so the read
fires many times, and records the (asset, offset) of the script PC at every genuine stop.
The offset is the prize -- it is the bytecode to disassemble.

Filters, both of them necessary:
  seg_0000:3d64  wait_loop, reported for any pause (CLAUDE.md)
  seg_0000:93b5  the AdLib sequencer, whose stream pointer wanders through this memory
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
ASSETS = {}
for n in sorted(os.listdir(GAME)):
    if n.lower().endswith(".io"):
        try: ASSETS[n] = decode(open(os.path.join(GAME, n), "rb").read())[0]
        except Exception: pass
PHANTOM = {0x3d64, 0x93b5}

def main():
    r0, c0 = int(sys.argv[1]), int(sys.argv[2])
    a, b = (sys.argv[3], sys.argv[4]) if len(sys.argv) > 4 else ("Left", "Right")
    secs = float(sys.argv[5]) if len(sys.argv) > 5 else 90.0
    addr = 0x129d0 + r0 * 90 + c0
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "MEMORY_READ", "condition": None})
    drv = os.path.join(os.environ.get("CLAUDE_JOB_DIR", "/tmp"), "tmp", "toggle.sh")
    os.makedirs(os.path.dirname(drv), exist_ok=True)
    open(drv, "w").write("#!/bin/sh\ncd %s\nwhile true; do\n tools/ish keys %s >/dev/null 2>&1\n"
                         " sleep 0.8\n tools/ish keys %s >/dev/null 2>&1\n sleep 0.8\ndone\n"
                         % (HERE, a, b))
    os.chmod(drv, 0o755)
    p = subprocess.Popen([drv])
    g = Rsp(st["gdb"])
    real, phantom, t0 = Counter(), 0, time.time()
    try:
        while time.time() - t0 < secs:
            g.cont()
            if g.wait_stop(timeout=secs - (time.time() - t0)) is None:
                break
            reg = g.registers()
            rel = reg["ip"] - load * 16
            if rel in PHANTOM:
                phantom += 1
                continue
            ds, si = reg["ds"], reg["si"] & 0xffff
            try:
                raw = g.read_mem(ds * 16 + si, 64)
            except Exception:
                continue
            hit = [(n, d.find(raw)) for n, d in ASSETS.items()
                   if d.find(raw) >= 0 and d.find(raw, d.find(raw) + 1) < 0]
            # seg_0000:7153 is the evaluator loop's return point, so the handler that did
            # the read has already returned and SI sits just past its operands. The bytes
            # immediately before SI are that expression's encoding.
            try:
                pre = g.read_mem(ds * 16 + si - 8, 8).hex()
            except Exception:
                pre = ""
            key = (hex(rel), hit[0][0], hit[0][1], pre) if len(hit) == 1 else (hex(rel), "?", -1, pre)
            real[key] += 1
    finally:
        p.terminate()
        mcp("clear_breakpoints"); g.cont()
    print(f"cell ({r0},{c0}) at {addr:#07x}: {sum(real.values())} genuine, {phantom} phantom")
    for (site, asset, off, pre), n in real.most_common(15):
        print(f"  site seg_0000:{site}  {asset} @{off}  before SI: {pre}  x{n}")

main()

#!/usr/bin/env python3
"""Which routine writes a given pixel of the viewport?

Hunting the drawing loops one at a time found the backdrop (fond.io through
seg_0e97:0660) and then failed twice on scenery and on characters. This is the method
that found the viewport routines in the first place: watch writes to the back buffer at
one screen position.

The back buffer is at 0xE0000 (ss:[1dbf] reads e000:0000) and the blit is 1:1, so the
byte for screen (x, y) is at 0xE0000 + y*320 + x.

A control breakpoint on memory the program never writes measures the phantom-stop rate,
which any pause produces; subtract it before believing anything.

    tools/t56-writer.py X Y [seconds]
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

def run(g, addr, secs, load, label):
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "MEMORY_WRITE", "condition": None})
    drv = os.path.join(os.environ.get("CLAUDE_JOB_DIR", "/tmp"), "tmp", "t56.sh")
    os.makedirs(os.path.dirname(drv), exist_ok=True)
    open(drv, "w").write("#!/bin/sh\ncd %s\nfor k in Left Right Left Right Left Right; do\n"
                         " tools/ish keys $k >/dev/null 2>&1\n sleep 1.2\ndone\n" % HERE)
    os.chmod(drv, 0o755)
    subprocess.Popen([drv])
    sites, t0 = Counter(), time.time()
    while time.time() - t0 < secs:
        g.cont()
        if g.wait_stop(timeout=secs - (time.time() - t0)) is None:
            break
        r = g.registers()
        sites[(r["cs"], r["ip"] - r["cs"] * 16)] += 1
    mcp("clear_breakpoints"); g.cont()
    print(f"{label}: {sum(sites.values())} stops at {len(sites)} sites")
    return sites

def main():
    x, y = int(sys.argv[1]), int(sys.argv[2])
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 45
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    # ONE connection for the whole run: Spice86's GDB stub accepts a single client and
    # does not come back after it closes, so a second Rsp() gets ECONNREFUSED and the
    # emulator has to be restarted.
    g = Rsp(st["gdb"])
    live = run(g, 0xE0000 + y * 320 + x, secs, load, f"viewport ({x},{y})")
    ctrl = run(g, 0xB8000, secs / 2, load, "control (never written)")
    print(f"\n  {'site':<28} {'live':>6} {'control':>8}")
    for (cs, off), n in live.most_common(14):
        c = ctrl.get((cs, off), 0)
        seg = "seg_0e97" if cs - load == 0x0e97 else \
              ("seg_0000" if cs == load else f"cs={cs:04x}")
        mark = "  <-- phantom" if c else ""
        print(f"  {seg}:{off & 0xffff:04x}{'':<14} {n:6} {c:8}{mark}")

main()

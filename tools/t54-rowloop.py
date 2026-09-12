#!/usr/bin/env python3
"""Read the viewport row loop's registers at the row step.

At seg_0e97:05f4 the loop has just finished a row and is about to apply the two per-row
deltas. CX is the pixel count for the row (restored from DX), BP the rows remaining.
If cs:[002e] is a shear it will differ from the buffer stride by something unrelated to
CX; if it is just "next row" it will equal stride +- CX exactly.
"""
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
from collections import Counter
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
    site = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x05f4
    want = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    seg = load + 0x0e97
    addr = seg * 16 + site
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
    g = Rsp(st["gdb"])
    drv = os.path.join(os.environ.get("CLAUDE_JOB_DIR", "/tmp"), "tmp", "t54drv.sh")
    os.makedirs(os.path.dirname(drv), exist_ok=True)
    open(drv, "w").write("#!/bin/sh\ncd %s\nfor k in Up Down Left Right Up Down; do\n"
                         " tools/ish keys $k >/dev/null 2>&1\n sleep 1.1\ndone\n" % HERE)
    os.chmod(drv, 0o755)
    subprocess.Popen([drv])
    rows, t0 = [], time.time()
    while time.time() - t0 < 40 and len(rows) < want:
        g.cont()
        if g.wait_stop(timeout=40 - (time.time() - t0)) is None:
            break
        r = g.registers()
        if r["ip"] != addr:            # not our breakpoint
            continue
        d = bytes.fromhex(mcp("read_memory",
                              {"segment": seg, "offset": 0x2c, "length": 4})["Data"])
        src = int.from_bytes(d[0:2], "little")
        dst = int.from_bytes(d[2:4], "little")
        rows.append((r["cx"] & 0xffff, r["dx"] & 0xffff, r["bp"] & 0xffff,
                     r["si"] & 0xffff, r["di"] & 0xffff, src, dst))
    mcp("clear_breakpoints"); g.cont()
    print(f"{len(rows)} stops at seg_0e97:{site:04x}")
    print(f"  {'CX':>5} {'DX':>5} {'BP':>5} {'SI':>6} {'DI':>6} {'src':>5} {'dst':>5}"
          f"  {'dst-DX':>7} {'dst+DX':>7}")
    for cx, dx, bp, si, di, src, dst in rows[:18]:
        print(f"  {cx:5} {dx:5} {bp:5} {si:6} {di:6} {src:5} {dst:5}"
              f"  {dst-dx:7} {dst+dx:7}")
    c = Counter((dst - dx) for _, dx, _, _, _, _, dst in rows)
    print("  dst - DX:", dict(c))
    w = Counter((dx, src) for _, dx, _, _, _, src, _ in rows)
    print(f"  distinct (pixels_per_row, src_skip) pairs: {len(w)}")
    for (dx, src), n in w.most_common(12):
        need = (dx + 1) // 2
        print(f"    {dx:4} px  src_skip {src:4}  -> source row stride {need + src:4}  x{n}")

main()

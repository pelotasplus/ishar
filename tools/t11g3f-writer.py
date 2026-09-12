#!/usr/bin/env python3
"""Who writes the party's region id?

The region id is the byte at global +0x3EAC (FORMATS 7.2g), i.e. es:[ss:[0bf6] + 0x3eac].
A MEMORY_WRITE breakpoint there, with the party driven across a region boundary, names the
writer.

A memory breakpoint has no IP to check against, so the guard is different: read the watched
byte at each stop and only believe a stop where it actually changed.
"""
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import ioscan
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
for _n in sorted(os.listdir(os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com"))):
    if _n.lower().endswith(".io"):
        try:
            ASSETS[_n] = ioscan.decode(open(os.path.join(
                HERE, "ishar_legend_of_the_fortress_DOSGamer.com", _n), "rb").read())[0]
        except Exception:
            pass

def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "Right"
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 90
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    ss = mcp("read_cpu_state")["SS"]
    p = bytes.fromhex(mcp("read_memory", {"segment": ss, "offset": 0x0bf6, "length": 4})["Data"])
    gbase = int.from_bytes(p[2:], "little") * 16 + int.from_bytes(p[:2], "little")
    addr = gbase + 0x3EAC
    print(f"global base {gbase:#07x}, region id at {addr:#07x}")
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "MEMORY_WRITE", "condition": None})
    g = Rsp(st["gdb"])
    drv = os.path.join(os.environ.get("CLAUDE_JOB_DIR", "/tmp"), "tmp", "t11g3f.sh")
    os.makedirs(os.path.dirname(drv), exist_ok=True)
    open(drv, "w").write("#!/bin/sh\ncd %s\nfor i in $(seq 1 40); do\n"
                         " tools/ish keys %s >/dev/null 2>&1\n sleep 1.0\ndone\n" % (HERE, key))
    os.chmod(drv, 0o755)
    subprocess.Popen([drv])
    prev, t0, seen = None, time.time(), []
    while time.time() - t0 < secs and len(seen) < 12:
        g.cont()
        if g.wait_stop(timeout=secs - (time.time() - t0)) is None:
            break
        r = g.registers()
        try:
            cur = g.read_mem(addr, 1)[0]
            pos = g.read_mem(gbase + 0x137C, 2)
        except Exception:
            continue
        if cur == prev:
            continue                      # the value did not change: not our write
        rel = r["ip"] - load * 16
        who = "?"
        # 0x26eb..0x26f8 is vm_run's fetch loop, so DS:SI is the script's program counter
        if 0x26eb <= rel <= 0x26f8:
            try:
                raw = g.read_mem(r["ds"] * 16 + (r["si"] & 0xffff), 64)
                hit = [(n, d.find(raw)) for n, d in ASSETS.items()
                       if d.find(raw) >= 0 and d.find(raw, d.find(raw) + 1) < 0]
                if len(hit) == 1:
                    who = f"{hit[0][0]} @{hit[0][1]}"
            except Exception:
                pass
        seen.append((prev, cur, rel, who, pos[0], pos[1]))
        print(f"  region {prev} -> {cur} at cell ({pos[0]},{pos[1]})   "
              f"ip = seg_0000:{rel:04x}   script {who}", flush=True)
        prev = cur
    mcp("clear_breakpoints"); g.cont()
    print(f"{len(seen)} value changes")

main()

#!/usr/bin/env python3
"""
T39c: where does main.io's script actually start?

Stepping tools/vmi.py from offset 0 dies after 23 statements, so the file does not
begin with executable script. Catch the FIRST entry to vm_run in the whole run and
record DS:SI -- that offset is the entry point, observed rather than guessed. Also
record the caller, because if the entry offset comes out of the asset header rather
than a constant, the same trick answers T37 for every asset.
"""
import json, os, sys, time, urllib.request
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
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:]); return j.get("result", {}).get("structuredContent", j)

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 90
want = int(sys.argv[2]) if len(sys.argv) > 2 else 6
load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
entry = load * 16 + 0x26eb                      # vm_run
g = Rsp(st["gdb"])
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
print(f"break at {entry:#x} = vm_run; waiting for the FIRST entry (load={load:#x})")

assets = {}
for n in sorted(os.listdir(GAME)):
    if n.lower().endswith(".io"):
        try: assets[n] = decode(open(os.path.join(GAME, n), "rb").read())[0]
        except Exception: pass

seen, t0 = 0, time.time()
while time.time() - t0 < secs and seen < want:
    g.cont()
    if g.wait_stop(timeout=max(1, secs - (time.time() - t0))) is None:
        continue
    r = g.registers()
    if r["ip"] != entry:
        continue
    seen += 1
    ds, si, ss, sp = r["ds"], r["si"] & 0xffff, r["ss"], r["sp"] & 0xffff
    lin = ds * 16 + si
    ret = int.from_bytes(g.read_mem(ss * 16 + sp, 2), "little")
    run = bytes(g.read_mem(lin, 64))
    owners = [n for n, d in assets.items() if d.find(run) >= 0]
    where = ""
    if len(owners) == 1:
        d = assets[owners[0]]
        i = d.find(run)
        if d.find(run, i + 1) < 0:
            where = f"{owners[0]} offset {i}"
        else:
            where = f"{owners[0]} (offset ambiguous)"
    elif owners:
        where = f"ambiguous across {len(owners)} assets"
    else:
        where = "in no asset (not a loaded script?)"
    print(f"  entry {seen}: DS:SI={ds:04x}:{si:04x}  caller seg_0000:{ret:04x}  -> {where}")
mcp("clear_breakpoints"); g.cont()

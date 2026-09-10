#!/usr/bin/env python3
"""
T37c: the FIRST vm_run entry for each asset that is not main.io.

T37b got main.io and logo.io (both offset 24) but ran out of wall clock at ~78s of
emulated boot, because every vm_run entry is a breakpoint stop and main.io supplies
thousands of them. frise.io and dplt.io were therefore caught mid-execution and their
entry points are unknown.

The fix is a condition: stop only when DS is not main.io's script segment. MCP-side
conditions filter properly (CLAUDE.md); GDB-side ones do not, which is why the
breakpoint is armed over MCP and waited on over GDB.

    tools/t37c-scan.py [seconds] [--exclude 1cf3,...]
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

secs = int(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else 240
excl = set()
if "--exclude" in sys.argv:
    excl = {int(x, 16) for x in sys.argv[sys.argv.index("--exclude") + 1].split(",")}

assets = {}
for n in sorted(os.listdir(GAME)):
    if n.lower().endswith(".io"):
        try: assets[n] = decode(open(os.path.join(GAME, n), "rb").read())[0]
        except Exception: pass

load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
entry = load * 16 + 0x26eb
cond = " && ".join(f"ds!=0x{s:04x}" for s in excl) if excl else None
g = Rsp(st["gdb"]); mcp("clear_breakpoints")
r = mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": cond})
print(f"break at {entry:#x} = vm_run, condition: {cond}")
g.cont()

seen_seg, first, t0 = {}, {}, time.time()
while time.time() - t0 < secs:
    g.cont()
    if g.wait_stop(timeout=max(1, secs - (time.time() - t0))) is None:
        continue
    r = g.registers()
    if r["ip"] != entry:
        continue
    ds, si = r["ds"], r["si"] & 0xffff
    if ds in excl:                       # belt and braces if the condition is ignored
        continue
    if ds in seen_seg:
        continue                         # only the FIRST entry per script segment matters
    lin = ds * 16 + si
    run = bytes(g.read_mem(lin, 64))
    cands = [(n, d.find(run)) for n, d in assets.items()
             if d.find(run) >= 0 and d.find(run, d.find(run) + 1) < 0]
    seen_seg[ds] = True
    if len(cands) == 1:
        n, i = cands[0]
        first[n] = i
        print(f"  {time.time()-t0:6.1f}s  DS={ds:04x} SI={si:04x}  -> {n} offset {i}")
    else:
        print(f"  {time.time()-t0:6.1f}s  DS={ds:04x} SI={si:04x}  -> "
              f"{'ambiguous across '+str(len(cands)) if cands else 'in no asset'}")
mcp("clear_breakpoints"); g.cont()
print("\nfirst entries:", json.dumps(first, indent=1))
json.dump(first, open(os.path.join(HERE, ".ish", "t37c.json"), "w"), indent=1)

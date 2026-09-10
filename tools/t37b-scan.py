#!/usr/bin/env python3
"""
T37b: which assets run script, and where does each one start?

vm_run's caller restores the script PC from es:[bp-8] (FORMATS 7.5), so every asset
running script shows up as a distinct DS:SI at the vm_run breakpoint. Sample it, match
each PC rigorously against the decoded assets, and report the offsets per asset -- the
lowest is the entry-point candidate.

Matching is deliberately strict. An earlier version matched a 24-byte run and took the
first asset alphabetically, and reported scripts in frise.io and then gerdep.io on
consecutive runs; both were wrong (FINDINGS 4.14). Here a run must be unique within its
asset AND absent from all 97 others.
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

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 120
assets = {}
for n in sorted(os.listdir(GAME)):
    if n.lower().endswith(".io"):
        try: assets[n] = decode(open(os.path.join(GAME, n), "rb").read())[0]
        except Exception: pass
load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
entry = load * 16 + 0x26eb
g = Rsp(st["gdb"]); mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
g.cont()
print(f"break at {entry:#x} = vm_run; scanning {secs}s")

bases, hits, first, unknown, t0 = {}, {}, {}, 0, time.time()
while time.time() - t0 < secs:
    g.cont()
    if g.wait_stop(timeout=max(1, secs - (time.time() - t0))) is None:
        continue
    r = g.registers()
    if r["ip"] != entry:
        continue
    lin = r["ds"] * 16 + (r["si"] & 0xffff)
    named = None
    for n, b in bases.items():
        if 0 <= lin - b < len(assets[n]):
            named = n; break
    if named is None:
        run = bytes(g.read_mem(lin, 64))
        cands = []
        for n, d in assets.items():
            i = d.find(run)
            if i >= 0 and d.find(run, i + 1) < 0:
                cands.append((n, i))
        if len(cands) == 1:
            n, i = cands[0]
            bases[n] = lin - i
            named = n
    if named:
        off = lin - bases[named]
        if named not in first:
            # From a PAUSED cold start the breakpoint catches every vm_run entry in
            # order, so the first offset seen for an asset is its entry point -- this
            # is how main.io's 24 was established (T39c).
            first[named] = (off, round(time.time() - t0, 1))
        hits.setdefault(named, set()).add(off)
    else:
        unknown += 1
mcp("clear_breakpoints"); g.cont()
print(f"\n{len(hits)} assets ran script; {unknown} samples unattributed")
for n, offs in sorted(hits.items(), key=lambda kv: -len(kv[1])):
    o = sorted(offs)
    f = first.get(n, ("?", "?"))
    print(f"  {n:16s} {len(o):4d} distinct offsets, lowest {o[0]}, highest {o[-1]}, "
          f"of {len(assets[n])} bytes   FIRST SEEN {f[0]} at t={f[1]}s")
json.dump({"offsets": {n: sorted(v) for n, v in hits.items()},
           "first": {n: v[0] for n, v in first.items()}},
          open(os.path.join(HERE, ".ish", "t37b.json"), "w"), indent=1)

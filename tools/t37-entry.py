#!/usr/bin/env python3
"""
T37: catch a script running inside an asset, and record where it entered.

vmcheck (T38) found every sampled DS:SI during gameplay landing inside frise.io,
an asset classified as graphics. T37's blocker is that vmdis has no entry point
for embedded scripts; an executing program counter IS one, observed rather than
guessed. This records the offsets.
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

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 60
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
hits, bases, t0 = {}, {}, time.time()
while time.time() - t0 < secs:
    g.cont()
    if g.wait_stop(timeout=max(1, secs - (time.time() - t0))) is None: continue
    r = g.registers()
    if r["ip"] != entry: continue
    ds, si = r["ds"], r["si"] & 0xffff
    lin = ds * 16 + si
    name = None
    for n, b in bases.items():                     # already-anchored assets are cheap
        o = lin - b
        if 0 <= o < len(assets[n]):
            name = n; break
    if name is None:
        run = bytes(g.read_mem(lin, 24))
        for n, d in assets.items():
            i = d.find(run)
            if i >= 0 and d.find(run, i + 1) < 0:
                bases[n] = lin - i; name = n; break
    if name:
        hits.setdefault(name, []).append(lin - bases[name])
mcp("clear_breakpoints"); g.cont()
for n, offs in sorted(hits.items(), key=lambda kv: -len(kv[1])):
    u = sorted(set(offs))
    print(f"{n}: {len(offs)} samples, {len(u)} distinct offsets, "
          f"range {u[0]}..{u[-1]} of {len(assets[n])} bytes")
    print("   lowest offsets seen:", u[:12])
json.dump({n: sorted(set(v)) for n, v in hits.items()},
          open(os.path.join(HERE, ".ish", "t37-entries.json"), "w"), indent=1)

#!/usr/bin/env python3
"""
T27: locate the running script.

vm_run (seg_0000:26eb) fetches its opcode from DS:SI, so SI is the script program
counter. Read the bytes around it, then search every decoded asset -- and the
executable -- for that exact run. Whatever contains it is where scripts live.
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
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:]); return j.get("result", {}).get("structuredContent", j)


load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
OFF = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x69ab
entry = load * 16 + OFF
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
# The stub only reports stops to a client that is driving it: if the machine is
# already free-running when we attach, `c` is a no-op and wait_stop times out --
# four runs returned zero hits that way, including one on a routine known to run
# thousands of times a second. Pause first, then let the loop resume it.
mcp("pause_emulator")
time.sleep(0.3)
print(f"breakpoint seg_0000:{OFF:04x} at {entry:#x}", flush=True)

samples = []
t0 = time.time()
while time.time() - t0 < 30 and len(samples) < 4:
    g.cont()
    if g.wait_stop(timeout=max(1, 30 - (time.time() - t0))) is None: break
    r = g.registers()
    if (r["ip"] & 0xffff) != OFF: continue
    ds, si = r["ds"] & 0xffff, r["si"] & 0xffff
    blob = g.read_mem(ds * 16 + si, 48)
    samples.append((ds, si, blob))
    print(f"  DS:SI={ds:04x}:{si:04x}  {blob[:24].hex()}", flush=True)
mcp("clear_breakpoints")
g.cont()

print("\nsearching the assets and the executable for those bytes...")
blobs = [b for _, _, b in samples if len(b) == 48]
cands = {}
for f in sorted(os.listdir(GAME)):
    if not f.lower().endswith((".io", ".fic")): continue
    try:
        d = decode(open(os.path.join(GAME, f), "rb").read())[0]
    except Exception:
        d = open(os.path.join(GAME, f), "rb").read()
    for b in blobs:
        i = d.find(b[:24])
        if i >= 0:
            cands.setdefault(f, []).append((i, b[:12].hex()))
exe = open(os.path.join(GAME, "start-unpacked.exe"), "rb").read()
for b in blobs:
    i = exe.find(b[:24])
    if i >= 0:
        cands.setdefault("start-unpacked.exe", []).append((i, b[:12].hex()))
if cands:
    for f, hits in cands.items():
        for off, pre in hits:
            print(f"  FOUND in {f} at offset {off}  ({pre}...)")
else:
    print("  not found in any asset or in the executable")

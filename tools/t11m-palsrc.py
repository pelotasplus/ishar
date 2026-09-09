#!/usr/bin/env python3
"""
T11m: find where the 768 palette bytes are read from, by watching them go out.

Searching the files for a captured DAC failed, which only means the copy in the
file is not byte-identical to the copy in the DAC. So ask the machine instead:
break where the game writes the DAC (seg_0e97:0d5f writes port 0x3c9), read the
source pointer, dump the 768 bytes it is reading, and then find *those* bytes in
the decoded assets. Whatever transformation sits in between stops mattering.
"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 45
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))


def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})


load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
entry = load * 16 + 0xe970 + 0xd5f          # seg_0e97:0d5f -- writes port 0x3c9
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
print(f"DAC writer at {entry:#x}; {BUDGET}s", flush=True)

out, t0 = [], time.time()
while time.time() - t0 < BUDGET and len(out) < 3:
    g.cont()
    if g.wait_stop(timeout=max(1, BUDGET - (time.time() - t0))) is None:
        break
    r = g.registers()
    if r["ip"] != entry:
        continue
    ds, si = r["ds"], r["si"] & 0xffff
    src = ds * 16 + si
    blob = g.read_mem(src, 768)
    ret = int.from_bytes(g.read_mem(r["ss"] * 16 + (r["sp"] & 0xffff), 2), "little")
    print(f"  DS:SI={ds:04x}:{si:04x} ({src:#07x})  CX={r['cx'] & 0xffff}  "
          f"ret {ret:#06x}  first={blob[:12].hex()}", flush=True)
    out.append({"src": src, "ds": ds, "si": si, "bytes": blob.hex()})

mcp("clear_breakpoints")
json.dump(out, open(os.path.join(HERE, ".ish", "palsrc.json"), "w"))
print(f"{len(out)} captures -> .ish/palsrc.json")
g.cont()

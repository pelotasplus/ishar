#!/usr/bin/env python3
"""
T29b: how is vm_statement_table (image 0x0060) indexed?

201 words is more than an unscaled opcode byte can reach and no
`jmp cs:[reg+0060]` exists in the image, so the dispatch uses some other form.
Break on a handler that is definitely in that table -- vm_prim_5args at
seg_0000:296b, listed at 0x198 -- and read the return address: that names the
dispatcher, and the bytes just before it say how the index is formed.
"""
import json, os, sys, time, urllib.request, collections
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 40
OFF = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x296b
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})
load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
entry = load*16 + OFF
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
print(f"seg_0000:{OFF:04x} at {entry:#x}; {BUDGET}s", flush=True)
seen = collections.Counter()
t0 = time.time()
while time.time() - t0 < BUDGET and sum(seen.values()) < 8:
    g.cont()
    if g.wait_stop(timeout=max(1, BUDGET-(time.time()-t0))) is None: break
    r = g.registers()
    if r["ip"] != entry: continue   # stub reports IP linear (T27b)
    ret = int.from_bytes(g.read_mem(r["ss"]*16 + (r["sp"] & 0xffff), 2), "little")
    seen[(ret, r["di"] & 0xffff, r["si"] & 0xffff)] += 1
mcp("clear_breakpoints")
print(f"\n{sum(seen.values())} hits")
for (ret, di, si), n in seen.most_common(8):
    print(f"  return {ret:#06x}  DI={di:#06x}  SI={si:#06x}  x{n}")
    if 0x100 <= ret <= 0x9410:
        b = g.read_mem(load*16 + ret - 12, 16)
        print(f"    bytes before the return site: {b.hex()}")
g.cont()

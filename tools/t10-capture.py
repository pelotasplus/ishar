#!/usr/bin/env python3
"""Capture the container decoder's input and output side by side (T10)."""
import json, os, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    body = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                       "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=body, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})
load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
entry = load*16 + 0x7a79
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type":"CPU_EXECUTION_ADDRESS", "condition": None})
t0 = time.time()
while time.time() - t0 < 70:
    g.cont()
    if g.wait_stop(timeout=70 - (time.time()-t0)) is None:
        sys.exit("no stop packet")
    r = g.registers()
    if r["ip"] == entry:
        break
else:
    sys.exit("never hit rle_decode_loop")
ss = r["ss"]
def w(off): return int.from_bytes(g.read_mem(ss*16+off, 2), "little")
mode = g.read_mem(ss*16+0x0b57, 1)[0]
print(f"rle_decode_loop hit at {time.time()-t0:.1f}s")
print(f"  mode ss:[0b57]={mode:#04x}  planes ss:[0b18]={w(0x0b18)}  buffer end ss:[0b3a]={w(0x0b3a):#06x}")
print(f"  input  ES:BX = {r['es']:04x}:{r['bx']&0xffff:04x}")
print(f"  output DS:SI = {r['ds']:04x}:{r['si']&0xffff:04x}")
inp = g.read_mem(r["es"]*16 + (r["bx"] & 0xffff), 48)
print(f"  input : {inp.hex(' ')}")
out_seg, out_off = r["ds"], r["si"] & 0xffff
mcp("clear_breakpoints")
g.cont()
time.sleep(3)
mcp("pause_emulator")
out = bytes.fromhex(mcp("read_memory", {"segment": out_seg, "offset": out_off, "length": 48})["Data"])
print(f"  output: {out.hex(' ')}")
json.dump({"mode": mode, "input": inp.hex(), "output": out.hex(),
           "input_at": f"{r['es']:04x}:{r['bx']&0xffff:04x}",
           "output_at": f"{out_seg:04x}:{out_off:04x}"},
          open(os.path.join(HERE, ".ish", "t10-capture.json"), "w"), indent=1)

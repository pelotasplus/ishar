#!/usr/bin/env python3
"""Capture the emulator's decoded bytes for logo.io -- ground truth for tools/io.py."""
import json, os, sys, time, urllib.request
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE,"tools"))
from rsp import Rsp
st=json.load(open(os.path.join(HERE,".ish","state.json")))
def mcp(t,a=None):
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":t,"arguments":a or {}}}).encode()
    r=urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp",data=body,method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r,timeout=60).read().decode().splitlines():
        if ln.startswith("data:"): return json.loads(ln[5:])["result"].get("structuredContent",{})
load=mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"]+0x10
g=Rsp(st["gdb"])
def brk(off, label, budget=90):
    lin=load*16+off
    mcp("clear_breakpoints"); mcp("add_breakpoint",{"address":lin,"type":"CPU_EXECUTION_ADDRESS","condition":None})
    t0=time.time()
    while time.time()-t0<budget:
        g.cont()
        if g.wait_stop(timeout=budget-(time.time()-t0)) is None: sys.exit(f"no stop waiting for {label}")
        r=g.registers()
        if r["ip"]==lin: return r
    sys.exit(f"never reached {label}")
import sys as _s
which = _s.argv[1] if len(_s.argv) > 1 else "logo"
if which == "main":
    hdr_at, close_at, sub = 0x7801, 0x7839, 22   # catalogue path
else:
    hdr_at, close_at, sub = 0x793a, 0x7978, 6    # direct path
r=brk(hdr_at, "header consumption")
ss=r["ss"]
def w(o): return int.from_bytes(g.read_mem(ss*16+o,2),"little")
hdr=[w(0x2480),w(0x2482),w(0x2484)]
out_off, out_seg = w(0x0bc8), w(0x0bca)
print(f"header words: {[hex(x) for x in hdr]}   output {out_seg:04x}:{out_off:04x}  stride sel ss:[0b57]={g.read_mem(ss*16+0x0b57,1)[0]:#04x}")
r=brk(close_at, "the close")
n=hdr[0]-sub
print(f"decoded length should be {n} bytes; dumping")
data=g.read_mem(out_seg*16+out_off, min(n, 0x10000))
out_path=os.path.join(HERE,".ish",f"{which}-decoded.bin")
open(out_path,"wb").write(data)
print(f"wrote {out_path} ({len(data)} bytes)")
print("first 32:", data[:32].hex(' '))

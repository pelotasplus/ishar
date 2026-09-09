#!/usr/bin/env python3
"""Find the code that reads an asset's head after decoding -- the directory parser."""
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
        if ln.startswith("data:"):
            res=json.loads(ln[5:])["result"]
            if res.get("isError"): raise RuntimeError(json.dumps(res)[:160])
            return res.get("structuredContent",{})
load=mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"]+0x10
g=Rsp(st["gdb"])
def name(cs, ip):
    rel=cs-load
    seg='seg_0000' if rel<0x941 else 'seg_0941' if rel<0xe97 else 'seg_0e97' if rel<0x13d7 else 'seg_13d7'
    base={'seg_0000':0,'seg_0941':0x941,'seg_0e97':0xe97,'seg_13d7':0x13d7}[seg]
    return f"{seg}:{(rel-base)*16 + (ip & 0xffff):04x}"
# stop where logo.io's header has just been read, so the buffer pointer is set
entry=load*16 + 0x793a
mcp("clear_breakpoints"); mcp("add_breakpoint",{"address":entry,"type":"CPU_EXECUTION_ADDRESS","condition":None})
t0=time.time()
while time.time()-t0 < 60:
    g.cont()
    if g.wait_stop(timeout=60) is None: sys.exit("no stop")
    r=g.registers()
    if r["ip"]==entry: break
ss=r["ss"]
def w(o): return int.from_bytes(g.read_mem(ss*16+o,2),"little")
buf = w(0x0bca)*16 + w(0x0bc8)
print(f"logo.io decode buffer at {w(0x0bca):04x}:{w(0x0bc8):04x} (linear {buf:#x})")
# watch reads of the head, past the 6-byte header the loader already consumed
target = buf + 992      # the palette, which we know is read
mcp("clear_breakpoints")
mcp("add_breakpoint",{"address":target,"type":"MEMORY_READ","condition":None})
print(f"watching reads of buffer+992 ({target:#x}) -- the palette")
seen={}
t0=time.time()
while time.time()-t0 < 45 and len(seen) < 8:
    g.cont()
    if g.wait_stop(timeout=45-(time.time()-t0)) is None: break
    r=g.registers()
    k=name(r["cs"], r["ip"])
    if k in seen: seen[k]+=1; continue
    seen[k]=1
    print(f"   read by {k}   DS:SI={r['ds']:04x}:{r['si']&0xffff:04x}  ES:DI={r['es']:04x}:{r['di']&0xffff:04x}")
mcp("clear_breakpoints"); g.cont()

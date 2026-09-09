#!/usr/bin/env python3
"""Break on DAC writes (port 0x3c9) and report who writes the palette, and from where."""
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
            if res.get("isError"): raise RuntimeError(json.dumps(res)[:200])
            return res.get("structuredContent",{})
load=mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"]+0x10
g=Rsp(st["gdb"])
mcp("clear_breakpoints")
# who FILLS the palette buffer at ss:0e46 (image 0xc0b0+0xe46)?
target = load*16 + 0xC0B0 + 0x0e46
print("breakpoint on writes to the palette buffer at", hex(target),
      mcp("add_breakpoint",{"address":target,"type":"MEMORY_WRITE","condition":None}))
t0=time.time(); seen={}
while time.time()-t0 < 60 and len(seen) < 6:
    g.cont()
    if g.wait_stop(timeout=60-(time.time()-t0)) is None: break
    r=g.registers()
    ss_=r["ss"]
    def w2(o): return int.from_bytes(g.read_mem(ss_*16+o,2),"little")
    cs, ip, ds, si = r["cs"], r["ip"], r["ds"], r["si"] & 0xffff
    rel = cs - load
    key=(rel, ip)
    if key in seen:
        seen[key]+=1; continue
    seen[key]=1
    seg = 'seg_0000' if rel<0x941 else 'seg_0941' if rel<0xe97 else 'seg_0e97' if rel<0x13d7 else 'seg_13d7'
    base = {'seg_0000':0,'seg_0941':0x941,'seg_0e97':0xe97,'seg_13d7':0x13d7}[seg]
    off = (rel-base)*16 + (ip & 0xffff)   # NOTE: ip is linear (T27b); see t11p-render
    ret = int.from_bytes(g.read_mem(r["ss"]*16 + (r["sp"] & 0xffff), 2), "little")
    buf_off, buf_seg = w2(0x0bc8), w2(0x0bca)
    src_rel = (ds*16 + si) - (buf_seg*16 + buf_off)
    print(f"  writer {seg}:{off:04x}  DS:SI={ds:04x}:{si:04x} (buffer+{src_rel})  "
          f"CX={r['cx']&0xffff}  DI={r['di']&0xffff:#06x}  ret {ret:#06x}")
mcp("clear_breakpoints"); g.cont()
print("distinct writers:", len(seen))

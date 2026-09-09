#!/usr/bin/env python3
"""Break where the sprite blitter reads its header and report the source pointer."""
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
# seg_0e97:0366 -- `add dx,[si+2]`, where SI points at a sprite header
entry=load*16 + 0xe970 + 0x38b   # seg_0e97:038b -- 445 calls during boot
mcp("clear_breakpoints")
mcp("add_breakpoint",{"address":entry,"type":"CPU_EXECUTION_ADDRESS","condition":None})
print(f"breakpoint at {entry:#x} (seg_0e97:038b)")
t0=time.time(); seen=0
while time.time()-t0 < 90 and seen < 10:
    g.cont()
    if g.wait_stop(timeout=90-(time.time()-t0)) is None: break
    r=g.registers()
    if r["ip"] != entry: continue
    seen+=1
    ss=r["ss"]
    def w(o): return int.from_bytes(g.read_mem(ss*16+o,2),"little")
    buf_off, buf_seg = w(0x0bc8), w(0x0bca)
    si, ds = r["si"] & 0xffff, r["ds"]
    src_lin = ds*16 + si
    buf_lin = buf_seg*16 + buf_off
    hdr = g.read_mem(src_lin, 8)
    ret = int.from_bytes(g.read_mem(r["ss"]*16 + (r["sp"] & 0xffff), 2), "little")
    import struct
    a,w1,h1,fl = struct.unpack("<4H", hdr)
    print(f"  hit {seen}: DS:SI={ds:04x}:{si:04x}  buffer={buf_seg:04x}:{buf_off:04x}  "
          f"header {[a,w1,h1,fl]} -> {w1+1}x{h1+1}  called from seg_0e97:{ret:04x}")
mcp("clear_breakpoints"); g.cont()

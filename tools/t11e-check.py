#!/usr/bin/env python3
"""Confirm catalogue ids against live loads: break on load_asset_by_id, log ss:[0b04]."""
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
g=Rsp(st["gdb"]); entry=load*16+0x78f9
mcp("clear_breakpoints"); mcp("add_breakpoint",{"address":entry,"type":"CPU_EXECUTION_ADDRESS","condition":None})
t0=time.time(); seen=[]
while time.time()-t0 < 45 and len(seen) < 12:
    g.cont()
    if g.wait_stop(timeout=45-(time.time()-t0)) is None: break
    r=g.registers()
    if r["ip"] != entry: continue
    aid=int.from_bytes(g.read_mem(r["ss"]*16+0x0b04, 2), "little")
    seen.append(aid)
    print(f"  {time.time()-t0:6.1f}s  load_asset_by_id  ss:[0b04] = {aid:#06x} ({aid})")
mcp("clear_breakpoints"); g.cont()
print("\nids requested, in order:", [hex(x) for x in seen])

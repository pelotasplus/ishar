#!/usr/bin/env python3
"""Capture VGA memory and the DAC while the Silmarils logo is up (T11b)."""
import json, os, sys, time, urllib.request
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE,"tools"))
import png
st=json.load(open(os.path.join(HERE,".ish","state.json")))
def mcp(t,a=None):
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":t,"arguments":a or {}}}).encode()
    r=urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp",data=body,method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r,timeout=60).read().decode().splitlines():
        if ln.startswith("data:"): return json.loads(ln[5:])["result"].get("structuredContent",{})
ref_path=os.path.join(HERE,"captures","trace-end.png")
_,_,ref=png.read(ref_path)
t0=time.time()
while time.time()-t0 < 120:
    shot=mcp("screenshot")["FilePath"]
    _,_,cur=png.read(shot)
    try:
        bad,tot=png.diff(cur,ref)
    except ValueError:
        time.sleep(3); continue
    if bad/tot <= 0.02:
        print(f"logo on screen after {time.time()-t0:.0f}s (match {100*(1-bad/tot):.1f}%)")
        break
    time.sleep(3)
else:
    sys.exit("logo never appeared")
vid=bytearray()
off=0
while len(vid) < 64000:
    take=min(4096, 64000-len(vid))
    vid += bytes.fromhex(mcp("read_memory", {"segment":0xa000+ (off>>4), "offset": off & 0xf, "length":take})["Data"])
    off += take
open(os.path.join(HERE,".ish","logo-vram.bin"),"wb").write(vid)
print(f"wrote .ish/logo-vram.bin ({len(vid)} bytes)")
pal=mcp("read_dac_palette")
json.dump(pal, open(os.path.join(HERE,".ish","logo-palette.json"),"w"))
print("palette keys:", list(pal)[:6])
print("vram[:24]:", vid[:24].hex(' '))

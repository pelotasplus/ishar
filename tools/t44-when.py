#!/usr/bin/env python3
"""Which assets' scripts run during a given window? Poll DS:SI filtered to vm_run."""
import json, os, sys, time, urllib.request
from collections import Counter
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ns = {}
exec(open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0], _ns)
decode = _ns["decode"]
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})
assets={}
for n in sorted(os.listdir(GAME)):
    if n.lower().endswith(".io"):
        try: assets[n]=decode(open(os.path.join(GAME,n),"rb").read())[0]
        except Exception: pass
LOAD = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
label, secs, cmd = sys.argv[1], float(sys.argv[2]), " ".join(sys.argv[3:])
import subprocess
if cmd: subprocess.Popen(cmd, shell=True)
hits=Counter(); tried={}; t0=time.time()
while time.time()-t0 < secs:
    c = mcp("read_cpu_state")
    if c["CS"] != LOAD or not (0x26eb <= c["IP"] <= 0x26f8): continue
    ds, si = c["DS"], c["ESI"] & 0xffff
    key=(ds, si//16)
    if key in tried:
        if tried[key]: hits[tried[key]] += 1
        continue
    raw=bytes.fromhex(mcp("read_memory",{"segment":ds,"offset":si,"length":64}).get("Data",""))
    owner=None
    if len(raw)==64:
        cands=[n for n,d in assets.items() if d.find(raw)>=0 and d.find(raw,d.find(raw)+1)<0]
        if len(cands)==1: owner=cands[0]
    tried[key]=owner
    if owner: hits[owner]+=1
print(f"[{label}] {sum(hits.values())} attributed samples: {hits.most_common(8)}")

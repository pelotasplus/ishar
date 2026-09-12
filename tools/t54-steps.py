#!/usr/bin/env python3
"""Tabulate the viewport's two per-row steps against the party's position.

viewport_row_loop ends with `add si, cs:[002c]` and `add di, cs:[002e]` -- a source
advance and a destination advance, both per row (FORMATS 3.13d). They are CS-relative
inside seg_0e97, so the segment is load + 0x0e97, NOT the load segment: read in the load
segment they come out 34 and 9982, which looks plausible and is wrong.

Sampled after a redraw settles, the pair describes the last row of the last object drawn.
"""
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:])["result"]
            return j.get("structuredContent", j)

def main():
    key = sys.argv[1]
    n = int(sys.argv[2])
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    seg = load + 0x0e97
    ss = mcp("read_cpu_state")["SS"]
    def rd(s, o, ln):
        return bytes.fromhex(mcp("read_memory", {"segment": s, "offset": o, "length": ln})["Data"])
    print(f"  {'pos':>10}  {'src':>6}  {'dst':>6}")
    for i in range(n):
        p = rd(ss, 0x644c, 2)
        d = rd(seg, 0x2c, 4)
        src = int.from_bytes(d[0:2], "little")
        dst = int.from_bytes(d[2:4], "little")
        print(f"  ({p[0]:2},{p[1]:2})  {src:6}  {dst:6}", flush=True)
        subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", key], capture_output=True)
        time.sleep(1.0)

main()

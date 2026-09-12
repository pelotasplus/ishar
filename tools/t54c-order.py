#!/usr/bin/env python3
"""Is the viewport's draw order repeatable for an unchanged scene?

T54c's last idea is to give objects an identity by their ORDINAL position in the draw
sequence -- the nth object is the nth object -- since three attempts at identity by sprite,
by tracking, and by the instance list have all failed. That only works if the order is
stable, which nothing has checked: FINDINGS calls it "probably back-to-front", a guess.

Nudges the party one way and back, so the scene returns to where it started, and compares
the two object sequences.

    tools/t54c-order.py [A B]      default Left Right
"""
import json, os, struct, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
QUIET = float(os.environ.get('QUIET', 2.5))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:])["result"]
            return j.get("structuredContent", j)

def frame(g, addr, key):
    subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", key], capture_output=True)
    rows, last = [], time.time()
    while time.time() - last < QUIET:
        g.cont()
        if g.wait_stop(timeout=QUIET) is None:
            break
        r = g.registers()
        if r["ip"] != addr:
            continue
        rows.append((r["si"] & 0xffff, r["dx"] & 0xffff, r["bp"] & 0xffff, r["di"] & 0xffff))
        last = time.time()
    objs, cur = [], []
    for row in rows:
        if cur and row[2] >= cur[-1][2]:
            objs.append(cur); cur = []
        cur.append(row)
    if cur:
        objs.append(cur)
    # one tuple per object: source offset, width, rows, origin
    return [(o[0][0], o[0][1], len(o), divmod(o[0][3], 320)[::-1]) for o in objs]

def main():
    a = sys.argv[1] if len(sys.argv) > 1 else "Left"
    b = sys.argv[2] if len(sys.argv) > 2 else "Right"
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    addr = (load + 0x0e97) * 16 + 0x059a
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
    g = Rsp(st["gdb"])
    seq = []
    for key in (a, b, a, b):
        f = frame(g, addr, key)
        seq.append((key, f))
        pos = bytes.fromhex(mcp("read_memory",
                {"segment": mcp("read_cpu_state")["SS"], "offset": 0x644c, "length": 2})["Data"])
        print(f"  {key:6} @({pos[0]},{pos[1]}) -> {len(f):3} objects  "
              f"{[(hex(s), w, str(o)) for s, w, n, o in f[:4]]}", flush=True)
    mcp("clear_breakpoints"); g.cont()
    # the two frames after `a` should describe the same scene, likewise the two after `b`
    for key in (a, b):
        fs = [f for k, f in seq if k == key]
        if len(fs) == 2 and fs[0] and fs[1]:
            same = fs[0] == fs[1]
            common = sum(1 for x, y in zip(fs[0], fs[1]) if x == y)
            print(f"\n  two frames after {key}: {len(fs[0])} vs {len(fs[1])} objects, "
                  f"{common} identical in the same position -- "
                  f"{'IDENTICAL' if same else 'DIFFERENT'}")

main()

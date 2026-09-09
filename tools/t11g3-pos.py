#!/usr/bin/env python3
"""
T11g3: find the party's map position in memory.

The editor prompts name POSITION X and POSITION Y (FORMATS.md 7.2), so the party
sits on the cont*.fic grid at some coordinate. Snapshot the data segment, take one
step, snapshot again, and keep the words that moved by exactly one -- a coordinate
changes by one per step and almost nothing else does.
"""
import json, os, struct, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))


def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=90).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:]); return j.get("result", {}).get("structuredContent", j)


sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
_g = Rsp(st["gdb"])


def snap(seg, size):
    """Read over GDB, not MCP: a 4KB read_memory call takes ~45s, this is instant."""
    return _g.read_mem(seg * 16, size)


load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
SS = load + 0x0c0b            # FINDINGS: SS = load + 0x0c0b
SIZE = 0x1000
key = sys.argv[1] if len(sys.argv) > 1 else "Up"
steps = int(sys.argv[2]) if len(sys.argv) > 2 else 3

print(f"watching ss:0000..{SIZE:04x} (SS={SS:04x}) across {steps} '{key}' steps", flush=True)
prev = snap(SS, SIZE)
cands = None
for s in range(steps):
    subprocess.run([os.path.join(HERE, "tools", "nudge.py"), key], capture_output=True)
    time.sleep(1.2)
    cur = snap(SS, SIZE)
    moved = set()
    for off in range(0, SIZE - 1, 2):
        a = struct.unpack_from("<H", prev, off)[0]
        b = struct.unpack_from("<H", cur, off)[0]
        if a != b and abs(b - a) <= 2:
            moved.add(off)
    cands = moved if cands is None else (cands & moved)
    print(f"  step {s+1}: {len(moved)} words moved by <=2, {len(cands)} consistent", flush=True)
    prev = cur
print(f"\ncandidate position words at ss:[offset]:")
for off in sorted(cands)[:20]:
    print(f"   ss:[{off:04x}] = {struct.unpack_from('<H', prev, off)[0]}")

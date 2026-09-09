#!/usr/bin/env python3
"""
T11p: name the viewport's routines by what counts up while walking.

Spice86 tracks a call count per function. Snapshot them, drive the party around,
snapshot again: the routines whose counts move are the ones drawing the 3D view.
No baseline file needed and no reliance on the listing, which has lost alignment
in the region the framebuffer writers live in.
"""
import json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 15


def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=120).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})


def snap():
    d = mcp("list_functions", {"limit": 5000})
    fs = d["Functions"] if isinstance(d, dict) and "Functions" in d else d
    return {(f["Address"]["Segment"], f["Address"]["Offset"]): f["CalledCount"] for f in fs}


load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
a = snap()
print(f"baseline: {len(a)} functions; walking for {SECONDS}s", flush=True)
t0 = time.time()
while time.time() - t0 < SECONDS:
    subprocess.run([os.path.join(HERE, "tools", "nudge.py"), "Down", "Right", "Up", "Left"],
                   capture_output=True)
b = snap()

delta = []
for k, v in b.items():
    d = v - a.get(k, 0)
    if d > 0:
        delta.append((d, k))
delta.sort(reverse=True)
print(f"\n{len(delta)} routines ran while walking; top by calls:")
print(f"{'calls':>10}  {'runtime':>10}  listing")
out = []
for d, (seg, off) in delta[:25]:
    rel = (seg - load) * 16 + off
    name = "?"
    for base, sname in ((0x0000, "seg_0000"), (0x9410, "seg_0941"),
                        (0xe970, "seg_0e97"), (0x13d70, "seg_13d7")):
        if rel >= base:
            name, boff = sname, rel - base
    print(f"{d:10d}  {seg:04x}:{off:04x}  {name}:{boff:04x}   (image+{rel:#07x})")
    out.append({"calls": d, "seg": seg, "off": off, "listing": f"{name}:{boff:04x}"})
json.dump(out, open(os.path.join(HERE, ".ish", "t11p-walk.json"), "w"), indent=1)

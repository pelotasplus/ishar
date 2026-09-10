#!/usr/bin/env python3
"""
Real timings for the boot sequence, without a breakpoint distorting them.

FINDINGS 4.9's wall times came from a run with a GDB breakpoint on every DOS file
call, which inflates everything. This samples the screen instead: a screenshot every
second, and a transition is logged when the frame changes by more than a threshold.
The emulator still pauses briefly per screenshot, but that is far cheaper than a stop
per file call.

    tools/t42-timeline.py [seconds] [--keys]     --keys drives Escape/Space/Kp1
"""
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import png
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 150
drive = "--keys" in sys.argv
prev, t0, marks = None, time.time(), []
while time.time() - t0 < secs:
    try:
        p = mcp("screenshot")["FilePath"]
        _, _, cur = png.read(p)
    except Exception:
        time.sleep(1); continue
    if prev is not None:
        try:
            bad, tot = png.diff(cur, prev)
            frac = bad / tot
        except ValueError:
            frac = 1.0
        if frac > 0.25:
            t = time.time() - t0
            marks.append((round(t, 1), round(100 * frac, 1)))
            print(f"  t={t:6.1f}s  screen changed {100*frac:5.1f}%")
    prev = cur
    if drive:
        for k in ("Escape", "Space", "Kp1"):
            mcp("send_keyboard_key", {"key": k, "isPressed": True})
            mcp("send_keyboard_key", {"key": k, "isPressed": False})
    time.sleep(1)
print(f"\n{len(marks)} transitions: {marks}")
json.dump(marks, open(os.path.join(HERE, ".ish", "t42-timeline.json"), "w"))

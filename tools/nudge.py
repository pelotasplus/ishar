#!/usr/bin/env python3
"""
Send keys to the running game, from outside the tracer.

The tracer has to sit blocked on the GDB socket to be fast, so it cannot also
send keys on a timer. This does it in a separate process: each keypress pauses
the emulator briefly, the stub reports that pause to the tracer, and the tracer
resumes it -- one continue per keypress instead of one per tick.

    tools/nudge.py [--every 8] [--select Kp1] [--seconds 120]
"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
every = float(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 8
select = sys.argv[sys.argv.index("--select") + 1] if "--select" in sys.argv else "Kp1"
secs = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 120


def mcp(tool, args):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=body,
                                 method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json, text/event-stream"})
    urllib.request.urlopen(req, timeout=30).read()


keys = (select, "Escape", "Space", "Escape")
t0 = time.time()
i = 0
while time.time() - t0 < secs:
    k = keys[i % len(keys)]
    i += 1
    try:
        mcp("send_keyboard_key", {"key": k, "isPressed": True})
        mcp("send_keyboard_key", {"key": k, "isPressed": False})
        print(f"{time.time()-t0:6.1f}s  {k}", file=sys.stderr)
    except Exception as e:
        print(f"nudge failed: {e}", file=sys.stderr)
        break
    time.sleep(every)

#!/usr/bin/env python3
"""
Drive Ishar's mouse by writing the variables its INT 33h callback would set.

The game installs an event handler (INT 33h AX=0x0c, mask 0x3f) at seg_0000:1249,
and Spice86 never invokes it -- `send_mouse_move` produces zero callback hits. But
the handler does nothing except store its arguments:

    1249  mov cs:[11c1], bx      ; button state
    124e  mov cs:[11bd], cx      ; x, range 0..319 (set by AX=07 at startup)
    1253  mov cs:[11bf], dx      ; y, range 0..199 (AX=08)
    1258  retf

and seg_0000:1259 reads them back. Writing the three words is therefore exactly
equivalent to the callback firing, and needs no emulator support.

    tools/mouse.py move 160 100
    tools/mouse.py click 44 132
"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
X, Y, BUTTONS = 0x11bd, 0x11bf, 0x11c1


def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:])
            return j.get("result", {}).get("structuredContent", j)


LOAD = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10


def poke(off, value):
    mcp("write_memory", {"address": LOAD * 16 + off,
                         "data": f"{value & 0xff:02x}{(value >> 8) & 0xff:02x}"})


def move(x, y):
    poke(X, x)
    poke(Y, y)


def click(x, y, hold=0.25):
    move(x, y)
    time.sleep(0.15)
    poke(BUTTONS, 1)
    time.sleep(hold)
    poke(BUTTONS, 0)


if __name__ == "__main__":
    cmd = sys.argv[1]
    x, y = int(sys.argv[2]), int(sys.argv[3])
    if cmd == "move":
        move(x, y)
    else:
        click(x, y)
    print(f"{cmd} {x},{y}")

#!/usr/bin/env python3
"""
Capture every sprite the game actually draws, straight out of emulator memory.

Guessing offsets statically failed (tools/ioscan.py: 1 real picture in 76). The
blitter, though, is handed a correct far pointer 445 times per boot, and the
8-byte header at that pointer carries the geometry. So: break on it, read the
pixels the emulator is about to draw, and write them out. No heuristics.

The offsets come back for free afterwards: the bytes read from memory are the
decoded file's bytes, so searching for them in our offline decode of each .io
recovers (file, offset) exactly -- which is the per-file directory T11k is after,
measured rather than inferred.

    tools/t11m-sprites.py [seconds]
"""
import json, os, struct, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 120
OUT = os.path.join(HERE, ".ish", "sprites.json")

st = json.load(open(os.path.join(HERE, ".ish", "state.json")))


def mcp(t, a=None):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=body, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})


load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
entry = load * 16 + 0xe970 + 0x38b          # seg_0e97:038b, the blitter
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
print(f"blitter breakpoint at {entry:#x}; {BUDGET}s budget", flush=True)

# Nothing is drawn while the game sits still, so keep poking it. Keys are
# enqueued and delivered when the machine resumes, so this works even though
# the breakpoint has it stopped most of the time.
KEYS = ["Escape", "Space", "Enter", "Down", "Right", "Up", "Left"]
last_key = [0.0, 0]


def poke():
    if time.time() - last_key[0] < 2.0:
        return
    k = KEYS[last_key[1] % len(KEYS)]
    last_key[0], last_key[1] = time.time(), last_key[1] + 1
    try:
        mcp("send_keyboard_key", {"key": k, "isPressed": True})
        mcp("send_keyboard_key", {"key": k, "isPressed": False})
    except Exception:
        pass


seen, sprites = set(), []
t0 = time.time()
while time.time() - t0 < BUDGET:
    poke()
    g.cont()
    if g.wait_stop(timeout=max(1, BUDGET - (time.time() - t0))) is None:
        break
    r = g.registers()
    if r["ip"] != entry:                    # MCP calls pause the machine too
        continue
    ds, si = r["ds"], r["si"] & 0xffff
    src = ds * 16 + si
    try:
        a, w1, h1, fl = struct.unpack("<4H", g.read_mem(src, 8))
    except Exception:
        continue
    w, h = w1 + 1, h1 + 1
    key = (src, w, h)
    if key in seen or not (0 < w <= 320 and 0 < h <= 200):
        continue
    seen.add(key)
    px = g.read_mem(src + 8, w * h)
    if len(px) != w * h:
        continue
    ss = r["ss"]
    buf = int.from_bytes(g.read_mem(ss * 16 + 0x0bca, 2), "little") * 16 + \
        int.from_bytes(g.read_mem(ss * 16 + 0x0bc8, 2), "little")
    sprites.append({"src": src, "w": w, "h": h, "word0": a, "flags": fl,
                    "buf": buf, "rel": src - buf, "px": px.hex()})
    print(f"  {len(sprites):3d}  {w}x{h}  flags={fl}  word0={a}  "
          f"at {src:#07x} (buffer+{src - buf})", flush=True)

mcp("clear_breakpoints")
try:
    pal = mcp("read_dac_palette") or {}
except Exception as e:
    print("palette read failed:", e)
    pal = {}
json.dump({"sprites": sprites, "palette": pal}, open(OUT, "w"))
print(f"{len(sprites)} distinct sprites -> {OUT}")
g.cont()

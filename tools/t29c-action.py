#!/usr/bin/env python3
"""
T29c: attribute VM opcodes to a game action by diffing call counts across it.

The walk diff (T29) only ever showed the language core, because domain verbs fire
once per event and drown in hundreds of thousands of eval/assign calls. The fix is
to make the action short and specific: snapshot, do one thing, snapshot again, and
report only the routines that are in vm_statement_table.

    tools/t29c-action.py click 63 133      # press a panel button
    tools/t29c-action.py key Up            # a keypress
    tools/t29c-action.py idle              # control: nothing at all
"""
import json, os, struct, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDR = 0x250
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))


def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=120).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})


img = open(os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com",
                        "start-unpacked.exe"), "rb").read()
TABLE = {}
for opc in range(231):
    w = struct.unpack_from("<H", img, HDR + 0x24 + opc * 2)[0]
    if 0x100 <= w <= 0x9410:
        TABLE[w] = opc


def snap():
    d = mcp("list_functions", {"limit": 5000})
    fs = d["Functions"] if isinstance(d, dict) and "Functions" in d else d
    return {(f["Address"]["Segment"], f["Address"]["Offset"]): f["CalledCount"] for f in fs}


load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
what = sys.argv[1] if len(sys.argv) > 1 else "idle"
a = snap()
if what == "click":
    x, y = int(sys.argv[2]), int(sys.argv[3])
    mcp("send_mouse_move", {"x": x, "y": y})
    time.sleep(0.4)
    mcp("send_mouse_button", {"button": "left", "isPressed": True})
    time.sleep(0.2)
    mcp("send_mouse_button", {"button": "left", "isPressed": False})
elif what == "key":
    for k in sys.argv[2:]:
        mcp("send_keyboard_key", {"key": k, "isPressed": True})
        time.sleep(0.12)
        mcp("send_keyboard_key", {"key": k, "isPressed": False})
time.sleep(1.5)
b = snap()

rows = []
for k, v in b.items():
    d = v - a.get(k, 0)
    if d <= 0:
        continue
    seg, off = k
    rel = (seg - load) * 16 + off
    rows.append((d, rel, TABLE.get(rel)))
rows.sort(reverse=True)
# Only routines the idle control never touched are evidence about the action:
# eval/assign run in the hundreds of thousands regardless.
base = set()
bp = os.path.join(HERE, ".ish", "t29c-idle.json")
if what != "idle" and os.path.exists(bp):
    base = {r["rel"] for r in json.load(open(bp))}
new = [r for r in rows if r[1] not in base]
print(f"action: {' '.join(sys.argv[1:]) or 'idle'} -- {len(rows)} routines ran, "
      f"{len(new)} NOT in the idle baseline\n")
if base:
    for d, rel, opc in new[:20]:
        tag = f"op {opc:3d} 0x{opc:02x}" if opc is not None else "(not a statement handler)"
        print(f"  NEW {d:7d} calls  seg_0000:{rel:04x}   {tag}")
    print()
print(f"{'calls':>9}  {'listing':>16}  opcode")
for d, rel, opc in rows[:30]:
    tag = f"op {opc:3d} 0x{opc:02x}" if opc is not None else ""
    print(f"{d:9d}  seg_0000:{rel:04x}   {tag}")
json.dump([{"calls": d, "rel": rel, "opcode": o} for d, rel, o in rows],
          open(os.path.join(HERE, ".ish", f"t29c-{what}.json"), "w"))

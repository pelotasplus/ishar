#!/usr/bin/env python3
"""
Trace the game's DOS file calls.

Breaks on the INT 21h handler with a condition, so the emulator only stops on
the calls we care about instead of all half-million of them, and records
filename, handle, length and buffer for each.

    tools/trace-io.py --until menu-language          # stop when that screen shows
    tools/trace-io.py --until game-party-panel --region 0,260,640,140
    tools/trace-io.py --seconds 120                  # or just run for a while
    tools/trace-io.py --opens-only                   # faster: opens and closes

Needs a running emulator (`tools/ish start`). Writes a table to stdout and the
raw events to .ish/io-trace.json.
"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import png  # noqa: E402

CAPS = os.path.join(HERE, "captures")
OPS = {0x3C: "create", 0x3D: "open", 0x3E: "close", 0x3F: "read",
       0x40: "write", 0x42: "seek", 0x4E: "findfirst", 0x4F: "findnext"}


def mcp(port, tool, args=None, timeout=60):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args or {}}}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/mcp", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(req, timeout=timeout).read().decode().splitlines():
        if ln.startswith("data:"):
            r = json.loads(ln[5:])["result"]
            if r.get("isError"):
                raise RuntimeError(json.dumps(r)[:200])
            return r.get("structuredContent", {})
    raise RuntimeError(f"no response to {tool}")


def cstring(port, seg, off, limit=80):
    data = bytes.fromhex(mcp(port, "read_memory",
                             {"segment": seg, "offset": off, "length": limit})["Data"])
    return data.split(b"\0")[0].decode("latin-1")


def main():
    st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
    port = st["port"]
    opens_only = "--opens-only" in sys.argv
    ops = [0x3D, 0x3E] if opens_only else [0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x42, 0x4E]
    cond = " || ".join(f"ah == {o:#04x}" for o in ops)

    ref = region = None
    if "--until" in sys.argv:
        name = sys.argv[sys.argv.index("--until") + 1]
        _, _, ref = png.read(os.path.join(CAPS, name + ".png"))
        if "--region" in sys.argv:
            region = [int(v) for v in sys.argv[sys.argv.index("--region") + 1].split(",")]
            ref = png.crop(ref, *region)
    seconds = int(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 60

    vec = bytes.fromhex(mcp(port, "read_memory",
                            {"segment": 0, "offset": 0x84, "length": 4})["Data"])
    entry = int.from_bytes(vec[2:4], "little") * 16 + int.from_bytes(vec[0:2], "little")

    mcp(port, "clear_breakpoints")
    mcp(port, "add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS",
                                 "condition": cond})
    print(f"INT 21h at {entry:#x}, condition: {cond}", file=sys.stderr)

    events, handles, deadline, last_check = [], {}, time.time() + seconds, 0.0
    while time.time() < deadline:
        mcp(port, "resume_emulator")
        # read_cpu_state pauses the emulator to take its reading, so finding
        # CS:IP at the INT 21h entry proves nothing on its own -- that address
        # is executed half a million times a run and a poll lands on it often.
        # A real breakpoint stop is STILL there on the next read, with the
        # cycle count unmoved; a poll that merely caught it in passing is not.
        # Poll gently. Every read_cpu_state pauses the emulator to take its
        # reading, so a tight loop spends most of the run stopped: at 0.02s the
        # boot did not reach the language menu in seven minutes of wall time.
        s = None
        for _ in range(600):
            a = mcp(port, "read_cpu_state")
            if a["CS"] * 16 + a["IP"] == entry:
                b = mcp(port, "read_cpu_state")
                if (b["CS"] * 16 + b["IP"] == entry
                        and b["Cycles"] == a["Cycles"]):
                    s = b
                    break
            time.sleep(0.2)

        if s is not None:
            ah = (s["EAX"] >> 8) & 0xFF
            ev = {"op": OPS.get(ah, f"{ah:#04x}"), "ah": ah, "cycles": s["Cycles"],
                  "bx": s["EBX"] & 0xFFFF, "cx": s["ECX"] & 0xFFFF,
                  "dx": s["EDX"] & 0xFFFF, "ds": s["DS"]}
            if ah in (0x3C, 0x3D, 0x4E):
                ev["name"] = cstring(port, s["DS"], s["EDX"] & 0xFFFF)
            if ah == 0x3F:
                ev["buffer"] = f"{s['DS']:04x}:{s['EDX'] & 0xFFFF:04x}"
                ev["length"] = s["ECX"] & 0xFFFF
            if ah == 0x42:
                ev["offset"] = ((s["ECX"] & 0xFFFF) << 16) | (s["EDX"] & 0xFFFF)
                ev["whence"] = s["EAX"] & 0xFF
            events.append(ev)

        if ref is not None and time.time() - last_check > 2:
            last_check = time.time()
            _, _, cur = png.read(mcp(port, "screenshot")["FilePath"])
            if region:
                cur = png.crop(cur, *region)
            try:
                bad, tot = png.diff(cur, ref)
            except ValueError:
                continue          # different video mode -- not this screen
            if bad / tot <= 0.01:
                print(f"target screen reached after {len(events)} calls", file=sys.stderr)
                break

    mcp(port, "clear_breakpoints")
    mcp(port, "resume_emulator")
    json.dump(events, open(os.path.join(HERE, ".ish", "io-trace.json"), "w"), indent=1)

    # Opens in order, with what each handle then did.
    print(f"\n{len(events)} DOS file calls\n")
    print(f"{'#':>3}  {'op':<9} {'file / detail':<28} {'cycles':>12}")
    for i, e in enumerate(events):
        detail = e.get("name", "")
        if e["op"] == "read":
            detail = f"handle {e['bx']:#x} -> {e['buffer']} {e['length']} bytes"
        elif e["op"] == "seek":
            detail = f"handle {e['bx']:#x} to {e['offset']:#x} whence {e['whence']}"
        elif e["op"] == "close":
            detail = f"handle {e['bx']:#x}"
        print(f"{i:>3}  {e['op']:<9} {detail:<28} {e['cycles']:>12}")


main()

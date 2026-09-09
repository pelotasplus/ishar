#!/usr/bin/env python3
"""
Trace the game's DOS file calls: MCP arms the breakpoint, GDB delivers the stops.

Neither half does this alone.

  * Over MCP, a conditional breakpoint filters properly -- but nothing tells the
    client when it fires, so tools/trace-io.py polls read_cpu_state, and every
    poll pauses the emulator. The traced boot runs ~10x slower than real time.
  * Over GDB, the stub PUSHES a stop packet, so the client blocks on a socket
    and the game runs full speed -- but conditions attached to a Z packet are
    ignored in this build (measured: `ah==0x3d`, spaced or not, single term or
    with ||, still stops on every INT 21h call, half a million of them).

So: set the conditional breakpoint through MCP, then sit on the GDB socket.
Spice86 notifies the GDB client on ANY pause, breakpoint or not, which is what
makes the combination work. Measured on the same milestone -- the boot's open
of logo.IO -- MCP polling took ~420s and this takes 7.5s.

    tools/ish start --gdb --pause
    tools/gdbtrace.py --until menu-language
    tools/gdbtrace.py --stop-after logo.IO --seconds 120

Writes .ish/io-trace-gdb.json and prints the table.
"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp  # noqa: E402
import png  # noqa: E402

CAPS = os.path.join(HERE, "captures")
OPS = {0x3C: "create", 0x3D: "open", 0x3E: "close", 0x3F: "read",
       0x40: "write", 0x42: "seek", 0x4E: "findfirst", 0x4F: "findnext"}


def main():
    st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
    if not st.get("gdb"):
        sys.exit("no GDB port -- start with `tools/ish start --gdb --pause`")

    def mcp(tool, args=None):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": tool, "arguments": args or {}}}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{st['port']}/mcp", data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream"})
        for ln in urllib.request.urlopen(req, timeout=60).read().decode().splitlines():
            if ln.startswith("data:"):
                return json.loads(ln[5:])["result"].get("structuredContent", {})
        raise RuntimeError(f"no response to {tool}")

    argv = sys.argv
    ops = ([0x3D, 0x3C, 0x3E, 0x4E] if "--opens-only" in argv
           else [0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x42, 0x4E])
    # 60s, not 300: an exploratory trace should end at the answer. Ask for more
    # only when the length of the run is the point.
    budget = int(argv[argv.index("--seconds") + 1]) if "--seconds" in argv else 60
    stop_after = argv[argv.index("--stop-after") + 1].lower() if "--stop-after" in argv else None
    ref = region = None
    if "--until" in argv:
        _, _, ref = png.read(os.path.join(CAPS, argv[argv.index("--until") + 1] + ".png"))
        if "--region" in argv:
            region = [int(v) for v in argv[argv.index("--region") + 1].split(",")]
            ref = png.crop(ref, *region)

    g = Rsp(st["gdb"])
    vec = g.read_mem(0x84, 4)
    entry = int.from_bytes(vec[2:4], "little") * 16 + int.from_bytes(vec[0:2], "little")
    cond = " || ".join(f"ah == {o:#04x}" for o in ops)
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS",
                           "condition": cond})
    print(f"INT 21h at {entry:#x}; MCP condition: {cond}", file=sys.stderr)

    nudge = "--nudge" in argv
    key_arg = argv[argv.index("--select") + 1] if "--select" in argv else "Kp1"
    NUDGE_KEYS = (key_arg, "Escape", "Space", "Escape")
    nudge_i = 0
    events, t0 = [], time.time()
    last_check = last_event = time.time()
    while time.time() - t0 < budget:
        g.cont()
        # Short waits, so the screen check and the nudges still happen during a
        # quiet phase. Blocking for the whole budget on a stop that is not
        # coming is how a 150s run sat on the logo screen doing nothing.
        # Block. The whole point of the GDB route is that the stub pushes a stop
        # packet; polling with a short timeout means a `c` every tick, and each
        # one is a pause/resume that costs more than it saves (measured: a 3.5s
        # startup took 27s at a 2s tick and 61s at 0.4s). Keys are sent by a
        # separate process (tools/nudge.py) so this can stay blocked.
        stop = g.wait_stop(timeout=min(15, max(1, budget - (time.time() - t0))))
        if stop is not None:
            r = g.registers()
            # Any pause reaches the GDB client, not just our breakpoint: the
            # screenshot and the key nudges below pause too. Only a stop AT the
            # breakpoint is an event.
            if r["ip"] == entry:
                ah = (r["ax"] >> 8) & 0xFF
                if ah in ops:
                    # An INT pushes flags, CS and IP, so the caller's return
                    # address sits at SS:SP. That is the game routine doing the
                    # file work -- the address worth annotating, unlike the DOS
                    # entry itself.
                    # The INT frame is IP, CS, FLAGS. The DOS wrappers push
                    # nothing before their `int 21h` and are reached by a near
                    # `call`, so the routine that actually wanted the file is one
                    # word further up, at SS:SP+6. Without it every caller reads
                    # as the wrapper itself, which names nothing.
                    frame = g.read_mem(r["ss"] * 16 + (r["sp"] & 0xFFFF), 10)
                    ev = {"op": OPS.get(ah, f"{ah:#04x}"), "ah": ah,
                          "wall": round(time.time() - t0, 2), "bx": r["bx"] & 0xFFFF,
                          "cx": r["cx"] & 0xFFFF, "dx": r["dx"] & 0xFFFF,
                          "ds": r["ds"],
                          "caller": f"{int.from_bytes(frame[2:4],'little'):04x}:"
                                    f"{int.from_bytes(frame[0:2],'little'):04x}",
                          # dos_open_asset pushes AX before its int 21h, so its
                          # caller is one word deeper than the others'. Reading
                          # +6 for every op reports `0002` -- the pushed AX --
                          # as the caller of every open.
                          "outer": f"{int.from_bytes(frame[8:10] if ah == 0x3D else frame[6:8], 'little'):04x}"}
                    if ah in (0x3C, 0x3D, 0x4E):
                        ev["name"] = g.read_mem(r["ds"] * 16 + (r["dx"] & 0xFFFF),
                                                64).split(b"\0")[0].decode("latin-1")
                    if ah == 0x3F:
                        ev["buffer"] = f"{r['ds']:04x}:{r['dx'] & 0xFFFF:04x}"
                        ev["length"] = r["cx"] & 0xFFFF
                    if ah == 0x42:
                        ev["offset"] = ((r["cx"] & 0xFFFF) << 16) | (r["dx"] & 0xFFFF)
                        ev["whence"] = r["ax"] & 0xFF
                    events.append(ev)
                    last_event = time.time()
                    if stop_after and ev.get("name", "").lower() == stop_after:
                        break

        # Nudge only when the game has gone quiet, and one key at a time. Every
        # MCP call pauses the emulator, and the GDB client has to continue it
        # again -- nudging three keys every five seconds regardless made a trace
        # that reaches an asset in 3.5s take 25s.
        if nudge and time.time() - last_event > 6:
            k = NUDGE_KEYS[nudge_i % len(NUDGE_KEYS)]
            nudge_i += 1
            last_event = time.time()
            mcp("send_keyboard_key", {"key": k, "isPressed": True})
            mcp("send_keyboard_key", {"key": k, "isPressed": False})
            # Each of those pauses the machine and the stub tells us about it.
            # Resume at once: waiting out the loop's timeout instead is what made
            # a 3.5s startup take 27s.
            g.cont()

        if ref is not None and time.time() - last_check > 3:
            last_check = time.time()
            _, _, cur = png.read(mcp("screenshot")["FilePath"])
            if region:
                cur = png.crop(cur, *region)
            try:
                bad, tot = png.diff(cur, ref)
            except ValueError:
                continue                   # different video mode -- not this screen
            if bad / tot <= 0.01:
                print(f"target screen reached after {len(events)} calls", file=sys.stderr)
                break

    mcp("clear_breakpoints")
    g.cont()
    json.dump(events, open(os.path.join(HERE, ".ish", "io-trace-gdb.json"), "w"), indent=1)
    print(f"\n{len(events)} DOS file calls in {time.time()-t0:.1f}s of wall clock\n")
    print(f"{'#':>3}  {'op':<9} {'file / detail':<38} {'caller':>11} {'outer':>6} "
          f"{'wall s':>7}")
    for i, e in enumerate(events):
        d = e.get("name", "")
        if e["op"] == "read":
            d = f"handle {e['bx']:#x} -> {e['buffer']} {e['length']} bytes"
        elif e["op"] == "seek":
            d = f"handle {e['bx']:#x} to {e['offset']:#x} whence {e['whence']}"
        elif e["op"] == "close":
            d = f"handle {e['bx']:#x}"
        print(f"{i:>3}  {e['op']:<9} {d:<38} {e.get('caller','-'):>11} "
              f"{e.get('outer','-'):>6} {e['wall']:>7}")


main()

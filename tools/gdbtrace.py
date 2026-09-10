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
    tools/gdbtrace.py --drive english --seconds 240   # drives the game ITSELF

--drive owns both halves of the run. Coordinating a separate nudge loop against a
separate trace window was got wrong three times in one session -- 70s windows on a
process that takes ~170s, so the interesting loads happened with nothing attached
and the trace honestly reported "0 calls". The tracer now sends the keys, so the
span it covers and the span it drives cannot disagree.

Writes .ish/io-trace-gdb.json and prints the table.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

# (keys sent once, keys repeated afterwards). Repeating the language key re-enters
# the menu instead of skipping the intro, which cost a 380s run that never left it.
# The language key belongs in the REPEAT list, not the one-shot list. The menu
# only appears ~88s into a cold boot (it waits on auteur.IO), so a single Kp1 at
# t=3s is pressed into the title screen and thrown away -- measured: the run sat
# on the menu for the remaining 60s. `ish boot` gets in because it cycles
# Kp1/Escape/Space every nudge, so the language key is still being offered when
# the menu finally shows up.
# (language key, keys pressed the whole time). The language key must arrive LATE
# and KEEP arriving:
#   * once at t=3s  -> pressed into the title screen and discarded; the run then
#                      sat on the language menu for its last 60s.
#   * every 3s from t=0 -> disrupts the early boot; MAIN.IO never even opened,
#                      8 file calls in 190s.
# So it starts after LANG_AFTER seconds and then repeats until the game takes it.
DRIVES = {
    "english": ("Kp1", ["Escape", "Space"]),
    "french":  ("Kp2", ["Escape", "Space"]),
    "german":  ("Kp3", ["Escape", "Space"]),
    "italian": ("Kp4", ["Escape", "Space"]),
    "walk":    (None,  ["Down", "Right", "Up", "Left"]),
}
LANG_AFTER = 45.0   # the menu shows up ~55-88s in; auteur.IO is the last file before it


def start_driver(name, seconds, send=None):
    """Send keys from a separate process for the whole trace, not a guessed window.

    Keys must come from another process: a blocking tracer that also wakes on a
    timer pays a pause per wake, measured at 3.5s -> 27s -> 61s as the timer gets
    faster (CLAUDE.md). A thread here only spawns nudge.py, it never touches the
    GDB socket.
    """
    seq = DRIVES.get(name)
    if not seq:
        raise SystemExit(f"--drive must be one of {', '.join(DRIVES)}")
    here = os.path.dirname(os.path.abspath(__file__))

    lang, repeat = seq

    def press(keys):
        """Send over MCP when a sender is given -- nudge.py did not reach the game.

        Measured: 180s of nudge.py Escape/Space left the title screen untouched,
        while `ish boot`, which sends the same keys over MCP, was in the game in
        16s and 3 nudges. Same keys, different transport, opposite outcome.
        """
        if send:
            for k in keys:
                send(k)
        else:
            subprocess.run([os.path.join(here, "nudge.py")] + keys, capture_output=True)

    def run():
        start = time.time()
        end = start + seconds
        time.sleep(3)
        while time.time() < end:
            keys = list(repeat)
            if lang and time.time() - start >= LANG_AFTER:
                keys = [lang] + keys
            press(keys)
            time.sleep(3)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def faulted(logpath):
    """Read the emulator log for a fault. Cheap: no MCP call, so no pause.

    A tracer that does not do this runs its whole budget against a dead machine
    and reports "no events", which reads like the game never did the thing.
    """
    try:
        txt = open(logpath, errors="ignore").read()
    except Exception:
        return None
    if "Emulation failed" not in txt and "halted" not in txt:
        return None
    m = re.search(r"Error is: (.+)", txt)
    return m.group(1).strip() if m else "emulation halted"
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp  # noqa: E402
import png  # noqa: E402

CAPS = os.path.join(HERE, "captures")
OPS = {0x3C: "create", 0x3D: "open", 0x3E: "close", 0x3F: "read",
       0x40: "write", 0x42: "seek", 0x4E: "findfirst", 0x4F: "findnext"}


def main():
    drive = None
    if "--drive" in sys.argv:
        drive = sys.argv[sys.argv.index("--drive") + 1]
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
    if drive:
        # start the keys AFTER the budget is known, so the driver runs exactly as
        # long as the trace does -- the mismatch this prevents is the whole point
        def send_key(k):
            mcp("send_keyboard_key", {"key": k, "isPressed": True})
            time.sleep(0.1)
            mcp("send_keyboard_key", {"key": k, "isPressed": False})
            time.sleep(0.2)

        start_driver(drive, budget, send=send_key)
        print(f"driving '{drive}' for the full {budget}s of the trace", flush=True)
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
    last_check = last_event = last_fault = time.time()
    logpath = st["log"]
    died = None
    while time.time() - t0 < budget:
        # Before anything else: is the machine still alive? A static screen is
        # not evidence of a slow phase, and a run that faults at second 12 will
        # otherwise sit out its full budget and report "no events".
        if time.time() - last_fault > 2:
            last_fault = time.time()
            died = faulted(logpath)
            if died:
                print(f"\nEMULATOR FAULTED after {time.time()-t0:.1f}s -- {died}",
                      file=sys.stderr)
                break
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

    # Save FIRST. A crashed emulator refuses the MCP socket, and cleaning up before
    # writing threw the traceback over a 44s trace and lost every event it had.
    json.dump(events, open(os.path.join(HERE, ".ish", "io-trace-gdb.json"), "w"), indent=1)
    for fn in (lambda: mcp("clear_breakpoints"), g.cont):
        try:
            fn()
        except Exception as e:
            print(f"(cleanup skipped: {type(e).__name__}) ", file=sys.stderr)
    print(f"\n{len(events)} DOS file calls in {time.time()-t0:.1f}s of wall clock"
          + (f"  -- RUN ENDED IN A FAULT: {died}" if died else "") + "\n")
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

#!/usr/bin/env python3
"""Map the VM global variable area by diffing it across one action at a time.

The globals are the game's state: the map sits at +0x0080, the party's row and column at
+0x137C, the region id at +0x3EAC (FORMATS 3.12), and everything else in there is
unnamed. A byte that moves when the party steps and at no other time belongs to stepping;
a byte that moves during every action including the idle control is a timer.

So: snapshot the area, perform one labelled action, snapshot again, and keep the spans
that differ. `idle` is the control -- it performs nothing, and whatever moves under it is
subtracted from every other action, which is the only way to see past the clock.
"""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import urllib.request

st = json.load(open(os.path.join(HERE, ".ish", "state.json")))

def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})

def ish(*args):
    subprocess.run([os.path.join(HERE, "tools", "ish"), *args], capture_output=True)

def mclick(x, y):
    subprocess.run([os.path.join(HERE, "tools", "mclick"), x, y, "--click"],
                   capture_output=True)

# label -> what to do. Nothing here is destructive: the ACTION menu opens and is closed
# again with Escape, and no verb is ever committed (a stray KILL once left the game in a
# state that could not be reasoned about).
ACTIONS = {
    "idle":    lambda: None,
    "wait10":  lambda: time.sleep(10),   # does anything advance on real time alone?
    "fwd":     lambda: ish("keys", "Up"),
    "back":    lambda: ish("keys", "Down"),
    "left":    lambda: ish("keys", "Left"),
    "right":   lambda: ish("keys", "Right"),
    "menu":    lambda: mclick("0.055", "0.663"),
    "esc":     lambda: ish("keys", "Escape"),
    "char2":   lambda: mclick("0.305", "0.663"),
    # EXIT in the right-hand verb column. The menu must always be closed again: run 1 of
    # this tool spent every action inside a dialog an earlier session had left open.
    "exitmenu": lambda: mclick("0.545", "0.963"),
}

def snap(g, base, n):
    b = bytearray()
    while len(b) < n:
        b += g.read_mem(base + len(b), min(4096, n - len(b)))
    v = bytearray()                    # the viewport is the proof an action did anything
    while len(v) < 64000:
        v += g.read_mem(0xa0000 + len(v), min(4096, 64000 - len(v)))
    g.cont()
    return bytes(b), bytes(v)

def spans(a, b, gap=4):
    """Changed offsets, coalesced into spans when they sit within `gap` of each other."""
    diff = [o for o in range(min(len(a), len(b))) if a[o] != b[o]]
    out = []
    for o in diff:
        if out and o - out[-1][1] <= gap:
            out[-1][1] = o
        else:
            out.append([o, o])
    return [(s, e) for s, e in out]

def main():
    size = 0x8000
    labels = sys.argv[1:] or ["idle", "fwd", "idle", "left", "right", "back"]
    bad = [l for l in labels if l not in ACTIONS]
    if bad:
        sys.exit(f"unknown action(s): {', '.join(bad)}  (have: {', '.join(ACTIONS)})")

    cpu = mcp("read_cpu_state")
    g = Rsp(st["gdb"])
    ptr = g.read_mem(cpu["SS"] * 16 + 0x0bf6, 4)
    g.cont()
    base = ((ptr[3] << 8 | ptr[2]) * 16) + (ptr[1] << 8 | ptr[0])
    print(f"SS={cpu['SS']:04x}  globals base ss:[0bf6] = "
          f"{ptr[3] << 8 | ptr[2]:04x}:{ptr[1] << 8 | ptr[0]:04x} = {base:#07x}, "
          f"{size} bytes")

    moved = {}                       # offset -> labels that changed it
    prev, pvram = snap(g, base, size)
    snaps = [prev]
    for i, label in enumerate(labels):
        ACTIONS[label]()
        time.sleep(1.3)
        cur, vram = snap(g, base, size)
        sp = spans(prev, cur)
        n = sum(1 for o in range(size) if prev[o] != cur[o])
        # An action that changed neither the screen nor the party's cell did nothing, and
        # the diff is then a measurement of the clock. The first run of this tool spent
        # six actions inside a modal dialog left open by an earlier session and reported
        # its timers as state.
        vch = sum(1 for a, b in zip(pvram, vram) if a != b) * 100.0 / 64000
        print(f"\n[{i}] {label}: {n} bytes moved in {len(sp)} spans, "
              f"screen {vch:.1f}% changed, party ({cur[0x137c]},{cur[0x137d]}) "
              f"facing {cur[0x137e]}")
        if vch < 0.5 and label != "idle":
            print("      !! screen did not change -- this action did nothing")
        pvram = vram
        snaps.append(cur)
        for s, e in sp[:24]:
            print(f"      +{s:04x}..{e:04x}  {prev[s:e+1][:12].hex()} -> {cur[s:e+1][:12].hex()}")
        if len(sp) > 24:
            print(f"      ... {len(sp) - 24} more spans")
        for o in range(size):
            if prev[o] != cur[o]:
                moved.setdefault(o, []).append(label)
        prev = cur

    # The control: anything that also moved under an idle is the clock, not the action.
    noise = {o for o, ls in moved.items() if "idle" in ls}
    print(f"\ncontrol: {len(noise)} bytes move with no input at all -- subtracted\n")
    print("offset  actions that moved it (idle-subtracted)")
    signal = {o: ls for o, ls in moved.items() if o not in noise}
    for o in sorted(signal):
        print(f"  +{o:04x}  {','.join(signal[o])}")
    print(f"\n{len(signal)} bytes carry action-specific state")
    # Keep every snapshot, not only the diff. Each run costs an emulator session and the
    # questions that follow -- what stride does a structure have, does a value return when
    # the party returns -- are all answerable offline from the bytes.
    out = os.path.join(HERE, ".ish", "t59-globals.json")
    json.dump({"base": base, "labels": labels,
               "moved": {f"{o:04x}": ls for o, ls in moved.items()},
               "noise": sorted(noise),
               "snaps": [s.hex() for s in snaps]}, open(out, "w"))
    print(f"-> {out}  ({len(snaps)} snapshots of {size} bytes)")

if __name__ == "__main__":
    main()

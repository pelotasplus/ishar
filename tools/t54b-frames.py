#!/usr/bin/env python3
"""Capture whole viewport frames, one per step, and report each object's sprite and place.

The earlier version drove the party and sampled for a fixed time, which caught partial
redraws: 14 objects at one cell, one or two at the next. This waits for **quiescence**
instead -- send one key, then collect until no stop has arrived for `QUIET` seconds. A
frame is whatever arrived in between, so it is whole or it is nothing.

At the row step BP counts the rows remaining for the object being drawn, so a run of
decreasing BP is one object; its first DI is the origin (y = DI // 320, x = DI % 320,
because the blit is 1:1), and DS:SI points into the source sprite.

    tools/t54b-frames.py KEY STEPS [site]
"""
import json, os, struct, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import ioscan, chains
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
QUIET = 2.5
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:])["result"]
            return j.get("structuredContent", j)

ASSETS, SPRITES = {}, {}
for n in sorted(os.listdir(GAME)):
    if n.lower().endswith(".io"):
        try:
            ASSETS[n] = ioscan.decode(open(os.path.join(GAME, n), "rb").read())[0]
        except Exception:
            pass

def sprite_at(name, off):
    if name not in SPRITES:
        SPRITES[name] = sorted((o, w, h) for c in chains.all_chains(ASSETS[name])
                               for o, w, h, _ in c)
    for o, w, h in SPRITES[name]:
        w0 = struct.unpack_from("<H", ASSETS[name], o)[0]
        hdr, bpp, _ = ioscan.MODES[w0 & 0xFF]
        if o <= off < o + hdr + ((w + 1) // 2 if bpp == 4 else w) * h:
            return o, w, h
    return None

def main():
    key = sys.argv[1]
    steps = int(sys.argv[2])
    site = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x059a
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    ss = mcp("read_cpu_state")["SS"]
    addr = (load + 0x0e97) * 16 + site
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
    g = Rsp(st["gdb"])
    for step in range(steps):
        subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", key], capture_output=True)
        rows, last = [], time.time()
        while time.time() - last < QUIET:
            g.cont()
            if g.wait_stop(timeout=QUIET) is None:
                break
            r = g.registers()
            if r["ip"] != addr:
                continue
            rows.append((r["ds"], r["si"] & 0xffff, r["dx"] & 0xffff,
                         r["bp"] & 0xffff, r["di"] & 0xffff))
            last = time.time()
        dumps = {}
        for ds in {d for d, *_ in rows}:
            try:
                dumps[ds] = g.read_mem(ds * 16, 0x10000)
            except Exception:
                pass
        pos = bytes.fromhex(mcp("read_memory",
                                {"segment": ss, "offset": 0x644c, "length": 2})["Data"])
        objs, cur = [], []
        for row in rows:
            if cur and row[3] >= cur[-1][3]:
                objs.append(cur); cur = []
            cur.append(row)
        if cur:
            objs.append(cur)
        print(f"\n--- after {key} #{step+1}: party ({pos[0]},{pos[1]}), "
              f"{len(rows)} rows in {len(objs)} objects")
        for o in objs:
            ds, si, dx, bp, di = o[0]
            d = dumps.get(ds)
            who = "?"
            if d and si + 48 <= len(d):
                probe = d[si:si + 48]
                if len(set(probe)) >= 4:
                    hit = [(n, a.find(probe)) for n, a in ASSETS.items()
                           if a.find(probe) >= 0 and a.find(probe, a.find(probe) + 1) < 0]
                    if len(hit) == 1:
                        sp = sprite_at(hit[0][0], hit[0][1])
                        who = f"{hit[0][0]} @{sp[0]} {sp[1]}x{sp[2]}" if sp else hit[0][0]
            y, x = divmod(di, 320)
            print(f"    {who:<28} {dx:3} px/row  at ({x:3},{y:3})  {len(o):3} rows", flush=True)
    mcp("clear_breakpoints"); g.cont()

main()

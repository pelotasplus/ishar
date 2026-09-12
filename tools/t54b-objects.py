#!/usr/bin/env python3
"""Group viewport rows into objects, and name the sprite each one is drawn from.

t55-source.py aggregates a frame; this keeps objects apart. At viewport_row_step_opaque
(seg_0e97:0660) BP counts the rows remaining for the object being drawn, so a run of stops
with BP decreasing by one is a single object. Its first row gives the origin: DI is the
destination pointer, and the blit is 1:1 (T54), so screen y = DI // 320, x = DI % 320.

    tools/t54b-objects.py [seconds]
"""
import json, os, struct, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
import ioscan, chains
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
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
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 45
    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    ss = mcp("read_cpu_state")["SS"]
    pos = bytes.fromhex(mcp("read_memory", {"segment": ss, "offset": 0x644c, "length": 2})["Data"])
    site = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x0660
    addr = (load + 0x0e97) * 16 + site
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": addr, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
    g = Rsp(st["gdb"])
    drv = os.path.join(os.environ.get("CLAUDE_JOB_DIR", "/tmp"), "tmp", "t54b.sh")
    os.makedirs(os.path.dirname(drv), exist_ok=True)
    open(drv, "w").write("#!/bin/sh\ncd %s\nfor k in Down Up Down Up Down Up; do\n"
                         " tools/ish keys $k >/dev/null 2>&1\n sleep 1.3\ndone\n" % HERE)
    os.chmod(drv, 0o755)
    subprocess.Popen([drv])
    rows, t0 = [], time.time()
    while time.time() - t0 < secs and len(rows) < 500:
        g.cont()
        if g.wait_stop(timeout=secs - (time.time() - t0)) is None:
            break
        r = g.registers()
        if r["ip"] != addr:
            continue
        rows.append((r["ds"], r["si"] & 0xffff, r["dx"] & 0xffff,
                     r["bp"] & 0xffff, r["di"] & 0xffff))
    segs = {ds for ds, *_ in rows}
    dumps = {}
    for ds in segs:
        try:
            dumps[ds] = g.read_mem(ds * 16, 0x10000)
        except Exception:
            pass
    mcp("clear_breakpoints"); g.cont()
    # split into objects: BP decreases within an object and jumps up at the next
    objs, cur = [], []
    for row in rows:
        if cur and row[3] >= cur[-1][3]:
            objs.append(cur); cur = []
        cur.append(row)
    if cur:
        objs.append(cur)
    print(f"party at ({pos[0]},{pos[1]}); {len(rows)} rows in {len(objs)} objects")
    print(f"  {'sprite':<26} {'drawn':>9} {'origin':>12} {'rows':>5}")
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
        print(f"  {who:<26} {dx:4} px/row {'(%d,%d)' % (x, y):>12} {len(o):5}")

main()

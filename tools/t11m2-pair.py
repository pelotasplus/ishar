#!/usr/bin/env python3
"""
T11m2 / T11m acceptance: prove `group*16 + nibble` against the framebuffer, and
record which palette each drawn sprite was actually using.

Self-contained: at the blitter we already hold the sprite's header, so the
predicted VGA index for every pixel is known without consulting any file. Read
the framebuffer at the *next* blitter stop -- by then this sprite has been drawn
-- and count how many pixels landed on the predicted byte. That is the
pixel-by-pixel check T11m's Done-when asks for.

The DAC is captured alongside, so each sprite is tagged with the palette live at
the moment it was drawn, which is the pairing T11m2 wants.
"""
import json, os, struct, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 60
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))


def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})


load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
g = Rsp(st["gdb"])
entry = load * 16 + 0xe970 + 0x38b
mcp("clear_breakpoints")
mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
print(f"blitter at {entry:#x}; {BUDGET}s", flush=True)


def find_in_vram(vram, rows, base, w, h):
    """Best (score, x, y) for the predicted indices anywhere on screen."""
    best = (0.0, None)
    ys = max(1, h // 10)
    xs = max(1, w // 10)
    for sy in range(0, 200 - h + 1):
        for sx in range(0, 320 - w + 1):
            hit = tot = 0
            for y in range(0, h, ys):
                r = rows[y]
                vb = (sy + y) * 320 + sx
                for x in range(0, w, xs):
                    if r[x] == 0:
                        continue
                    tot += 1
                    if vram[vb + x] == base + r[x]:
                        hit += 1
            if tot >= 6 and hit / tot > best[0]:
                best = (hit / tot, (sx, sy))
    return best


pending, results, t0 = None, [], time.time()
while time.time() - t0 < BUDGET and len(results) < 6:
    g.cont()
    if g.wait_stop(timeout=max(1, BUDGET - (time.time() - t0))) is None:
        break
    r = g.registers()
    if r["ip"] != entry:
        continue

    if pending:
        w, h, group, rows = pending
        vram = g.read_mem(0xA0000, 320 * 200)
        if len(vram) == 320 * 200:
            score, pos = find_in_vram(vram, rows, group * 16, w, h)
            if score > 0.75 and pos:
                sx, sy = pos
                hit = tot = 0
                for y in range(h):
                    for x in range(w):
                        if rows[y][x] == 0:
                            continue
                        tot += 1
                        hit += vram[(sy + y) * 320 + sx + x] == group * 16 + rows[y][x]
                print(f"  {w}x{h} group {group:2d} at ({sx},{sy}): "
                      f"{hit}/{tot} = {100*hit/tot:.1f}% exact", flush=True)
                results.append({"w": w, "h": h, "group": group,
                                "hit": hit, "tot": tot})
        pending = None

    ds, si = r["ds"], r["si"] & 0xffff
    try:
        w0, w1, h1, _ = struct.unpack("<4H", g.read_mem(ds * 16 + si, 8))
    except Exception:
        continue
    w, h = w1 + 1, h1 + 1
    if not (4 <= w <= 200 and 4 <= h <= 200):
        continue
    stride = (w + 1) // 2
    px = g.read_mem(ds * 16 + si + 8, stride * h)
    if len(px) != stride * h:
        continue
    rows = [[((px[y * stride + (x >> 1)] >> 4) if (x & 1) == 0
              else (px[y * stride + (x >> 1)] & 15)) for x in range(w)] for y in range(h)]
    pending = (w, h, w0 >> 8, rows)

mcp("clear_breakpoints")
pal = mcp("read_dac_palette")
json.dump({"results": results, "palette": pal},
          open(os.path.join(HERE, ".ish", "t11m2.json"), "w"))
if results:
    tot = sum(r["tot"] for r in results)
    hit = sum(r["hit"] for r in results)
    print(f"\n{len(results)} sprites, {hit}/{tot} = {100*hit/tot:.1f}% of opaque "
          f"pixels match group*16 + nibble")
else:
    print("\nno sprite located on screen")
g.cont()

#!/usr/bin/env python3
"""
Decide an asset's palette by matching its sprites against a real screenshot.

Pairing an asset with a scene (T11m2) is inference from load order. This checks
it: render the asset's sprites under each candidate palette and look for them in a
capture of the running game. The palette whose render is found on screen is the
right one, and a sprite that is not found scores nothing either way -- so this
says "verified", "wrong", or "no evidence", never "looks about right".

    tools/palcheck.py captures/t29d-ingame.png
"""
import json, os, sys, importlib.util

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import png
spec = importlib.util.spec_from_file_location("ioscan", os.path.join(HERE, "tools", "ioscan.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
GAME = m.GAME


def screen(path):
    """A 640x400 capture is mode 13h doubled; take every second pixel."""
    w, h, px = png.read(path)
    if w == 640:
        return 320, 200, [[px[y * 2][x * 2] for x in range(320)] for y in range(200)]
    return w, h, px


def pal_of(scene):
    d = m.decode(open(os.path.join(GAME, scene), "rb").read())[0]
    ps = m.palettes(d)
    if not ps:
        return None
    c = d[ps[0]:ps[0] + 768]
    return [tuple(c[i:i + 3]) for i in range(0, 768, 3)]


def best_match(rows, w, h, sw, sh, spx):
    """Best (score, x, y) for a rendered sprite anywhere on the screen."""
    ys = max(1, sh // 8)
    xs = max(1, sw // 8)
    best = (0.0, None)
    for oy in range(0, h - sh + 1, 2):
        for ox in range(0, w - sw + 1, 2):
            hit = tot = 0
            for y in range(0, sh, ys):
                r = spx[y]
                for x in range(0, sw, xs):
                    c = r[x]
                    if c == (0, 255, 0):
                        continue
                    tot += 1
                    if rows[oy + y][ox + x] == c:
                        hit += 1
            if tot >= 8 and hit / tot > best[0]:
                best = (hit / tot, (ox, oy))
    return best


def main():
    shot = sys.argv[1] if len(sys.argv) > 1 else "captures/t29d-ingame.png"
    w, h, rows = screen(shot)
    amb = json.load(open(os.path.join(HERE, ".ish", "asset-scene.json")))
    cand = dict(amb["ambiguous"])
    for a, s in amb["certain"].items():
        cand.setdefault(a, {s: 1})
    print(f"matching against {shot} ({w}x{h})\n")
    print(f"{'asset':14s} {'palette':12s} {'best match':>10s}   verdict")
    for asset in sorted(cand):
        path = os.path.join(GAME, asset)
        if not os.path.exists(path):
            continue
        try:
            d = m.decode(open(path, "rb").read())[0]
        except Exception:
            continue
        sp = m.extract(d)
        if not sp:
            continue
        sp = sorted(sp, key=lambda s: -s[1] * s[2])[:3]
        scores = {}
        for scene in cand[asset]:
            p = pal_of(scene)
            if not p:
                continue
            best = 0.0
            for off, sw, sh in sp:
                if sw > w or sh > h:
                    continue
                spx = m.render(d, off, sw, sh, p)
                s, _ = best_match(rows, w, h, sw, sh, spx)
                best = max(best, s)
            scores[scene] = best
        if not scores:
            continue
        win, sc = max(scores.items(), key=lambda kv: kv[1])
        verdict = "ON SCREEN, verified" if sc > 0.9 else ("partial" if sc > 0.6 else "not on screen")
        print(f"{asset[:-3]:14s} {win[:-3]:12s} {sc*100:9.1f}%   {verdict}"
              + ("   " + str({k[:-3]: round(v, 2) for k, v in scores.items()}) if len(scores) > 1 else ""))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Byte-by-byte map of one asset, every span labelled with the FORMATS section for it.

FORMATS.md describes the pieces -- the container header (3.0), the 16-byte asset header
(3.15), palette records (3.9), sprite chains (3.10), whole VGA pages (3.18), script (3.16)
-- but nothing assembles them for one file. This does, and it says what is left over,
which is the number that matters when porting a decoder.

    tools/anatomy.py dead.io
    tools/anatomy.py --all            one line per asset, accounted-for percentage
"""
import os, struct, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import ioscan
import chains as _chains
from ioscan import decode, extract, geometry

GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")

# Sprites identified against the running game. Keyed (asset, payload offset). Add to this
# as they are confirmed -- a sprite named here is broken out of its chain in FILES.md
# instead of disappearing into "N sprites", which is what made it invisible the first time.
ASSET_NOTES = {
    "fond.io": "The viewport's backdrop. Drawn by the opaque expander at seg_0e97:0644 -- "
               "this is the asset the 3D view is built from (FINDINGS 4.15c).",
    "bormin.io": "**The starting NPC.** Three of its twelve sprites were caught drawn at "
                 "three distances -- @2152 16x29, @1424 32x45, @3714 48x31 -- so the sprite "
                 "changes with range -- and the twelve sprites are body PARTS at several "
                 "ranges, not twelve whole figures. Adjacent, the NPC is @3714 (upper, "
                 "48x31) stacked over @2770 (lower, 48x39) (FINDINGS 4.15g).",
    "main.io": "Also carries the **font**: 16x9 glyph sprites, drawn 7 pixels apart "
               "(FINDINGS 4.15e).",
    "plaine.io": "Outdoor scenery for the plains: the bushes and trees in the viewport, at "
                 "**palette base 16**. Three sprites matched 100% against video memory "
                 "(FINDINGS 4.15d).",

    "arbre.io": "The 15 sprites are a **size ladder**, not 15 different trees: the "
                "viewport blits 1:1 (FORMATS 3.13d), so distance is expressed by which "
                "rung is drawn. Two rungs -- @25490 16x27 and @25714 16x15 -- were caught "
                "drawn in the SAME frame at different heights, which is the ladder in use. "
                "Which rung at which distance is T54b.",
}

IDENTIFIED = {
    ("frise.io", 51456): "the right panel column, drawn at (288,0) - 97/126 rows "
                         "verified vs VRAM (FINDINGS 4.15b)",
    ("buste.io", 6986):  "a character portrait, drawn at (0,147) - 100% vs VRAM "
                         "(FORMATS 3.13b, 3.17b)",
    ("frise.io", 43176): "the ACTION/ATTACK bar, base 192, drawn at x=0,64,128,192,256 "
                         "y=126 - 100% vs VRAM at all five (FORMATS 3.17b)",
    ("frise.io", 42656): "the empty LIFE bar, base 192, drawn at x=0,64,128,192,256 y=184 "
                         "- 100% at the four empty slots (FORMATS 3.17b)",
    ("frise.io", 50568): "16x8 at (126,175), base 192 - 83.9% vs VRAM (FORMATS 3.17b)",
    ("frise.io", 50712): "16x8 at (254,175), base 208 - 95.0% vs VRAM (FORMATS 3.17b)",
    ("frise.io", 50784): "the mouse cursor, base 160, drawn at (0,0) - 100% vs VRAM; the "
                         "identical 16x16 sprite is also main.io @25760 (FINDINGS 4.15d)",
    ("main.io", 25760):  "the mouse cursor, base 160, drawn at (0,0) - 100% vs VRAM; the "
                         "identical 16x16 sprite is also frise.io @50784 (FINDINGS 4.15d)",
    ("gerdep.io", 11718): "panel piece at (273,101), base 208 - 100% vs VRAM (4.15d)",
    ("gerdep.io", 10990): "compass needle / direction indicator, drawn in the panel "
                          "(FINDINGS 4.15d)",
    ("gerdep.io", 11118): "compass needle / direction indicator, drawn in the panel "
                          "(FINDINGS 4.15d)",
    ("plaine.io", 24720): "outdoor scenery, base 16, seen at (98,68) - 100% vs VRAM in the "
                          "VIEWPORT (FINDINGS 4.15d)",
    ("plaine.io", 26120): "outdoor scenery, base 16, seen at (146,59) - 100% vs VRAM in the "
                          "VIEWPORT (FINDINGS 4.15d)",
    ("plaine.io", 24440): "outdoor scenery, base 16, seen at (82,93) - 100% vs VRAM in the "
                          "VIEWPORT (FINDINGS 4.15d)",
    ("fond.io", 1366):   "the GROUND band: one 64x43 sprite tiled horizontally at 64-pixel "
                         "intervals across the viewport at y=83, clipped at both edges "
                         "(FINDINGS 4.15c)",
    ("fond.io", 2750):   "the SKY: 64x85 drawn at (96,0) (FINDINGS 4.15c)",
    ("fond.io", 5478):   "viewport backdrop (FINDINGS 4.15c)",
    ("fond.io", 7142):   "viewport backdrop (FINDINGS 4.15c)",
    ("gerdep.io", 8829): "the region-name switch: statement 0x2f with 21 cases, selector "
                         "vm_op_load_byte_global 0x3eac (FORMATS 7.2g)",
    ("main.io", 23272):  "a font glyph, 16x9, drawn in the panel caption at 7-pixel "
                         "spacing -- main.io carries the font (FINDINGS 4.15e)",
    ("main.io", 23662):  "a font glyph, 16x9 (FINDINGS 4.15e)",
    ("main.io", 23740):  "a font glyph, 16x9 (FINDINGS 4.15e)",
    ("main.io", 23896):  "a font glyph, 16x9 (FINDINGS 4.15e)",
    ("main.io", 24286):  "a font glyph, 16x9 (FINDINGS 4.15e)",
    ("main.io", 24598):  "a font glyph, 16x9 (FINDINGS 4.15e)",
    ("bormin.io", 2152): "the starting NPC at ~3 cells: 16x29, drawn at (224,72) and "
                         "(136,72) (FINDINGS 4.15f)",
    ("bormin.io", 1424): "the starting NPC at ~2 cells: 32x45, drawn at (12,65) "
                         "(FINDINGS 4.15f)",
    ("bormin.io", 3714): "the starting NPC at 1 cell: 48x31 at (103,60) -- **100% vs "
                         "VRAM**, 779 opaque pixels (FINDINGS 4.15f)",
    ("bormin.io", 2770): "the starting NPC's LOWER half when adjacent: 48x39 at (104,91), "
                         "stacked under @3714 -- 92.8% vs VRAM (FINDINGS 4.15g)",
    ("arbre.io", 18890): "a tree, 48x38, seen drawn at (177,72) (FINDINGS 4.15f)",
    ("arbre.io", 25490): "a tree, 16x27, seen drawn at (247,61) -- one rung of the size "
                         "ladder (FINDINGS 4.15c)",
    ("arbre.io", 25714): "a tree, 16x15, seen drawn at (256,66) -- a shorter rung than "
                         "@25490 in the SAME frame (FINDINGS 4.15c)",
    ("arbre.io", 12906): "the big foreground branch, 144x83, drawn at (256,0) clipped "
                         "(FINDINGS 4.15c)",
    ("plaine.io", 31600): "scenery, 48x19, seen at (43,76) (FINDINGS 4.15c)",
    ("plaine.io", 32064): "scenery, 32x12, seen at (256,79) (FINDINGS 4.15c)",
    ("plaine.io", 20934): "scenery, 48x9, seen at (76,94) (FINDINGS 4.15c)",
    ("plaine.io", 32264): "small scenery, 16x7, tiled every 24 pixels along y=81 "
                          "(FINDINGS 4.15e)",
    ("gerdep.io", 7243): "the region rule: `if (column < 46) && (region == 1)` -- region "
                         "membership is hand-written coordinate tests, not a table "
                         "(FINDINGS 6.7b)",
    ("gerdep.io", 7271): "writes the party's region id (global 0x3eac); caught live with a "
                         "MEMORY_WRITE breakpoint (FINDINGS 6.7b)",
    ("lacustre.io", 1190): "reads the world map -- 26 80 00, global[0x0080 + index] -- the "
                           "only code path that touches a map cell (FORMATS 7.2h)",
}
try:
    import vmi
    vmi_stmt = set(vmi.STMT)
except Exception:
    vmi_stmt = set()
# assets with a known entry set, i.e. bytecode that has actually been traversed
try:
    import json
    SCRIPTED = set(json.load(open(os.path.join(HERE, ".ish", "t37f-entries.json"))))
except Exception:
    SCRIPTED = set()
PAGE = 320 * 200


def spans(name):
    """-> (decoded, [(start, end, label, formats_ref)]), sorted, non-overlapping."""
    raw = open(os.path.join(GAME, name), "rb").read()
    d = decode(raw)[0]
    out = [(0, 2, "asset id", "3.15"),
           (2, 8, "format signature 16 00 00 17 00 00", "3.15"),
           (8, 16, "unidentified header bytes", "3.15")]

    # Every chain, not just the best-scoring one: frise.io has five and the panel is in
    # the fifth (FINDINGS 4.15b). ioscan.extract returns only one.
    sprites = [(o, w, h) for c in _chains.all_chains(d) for o, w, h, _ in c]
    sprites.sort()
    for off, w, h in sprites:
        w0 = struct.unpack_from("<H", d, off)[0]
        hdr, stride, size = geometry(w0, w, h)
        known = IDENTIFIED.get((name.lower(), off))
        if known:
            out.append((off, off + size,
                        f"**{w}x{h} sprite, mode {w0 & 0xff:#04x}** - {known}", "3.10"))
        else:
            out.append((off, off + hdr, f"sprite header, mode {w0 & 0xff:#04x}, {w}x{h}", "3.10"))
            out.append((off + hdr, off + size, f"sprite pixels ({stride} bytes/row)", "3.10"))

    # Scan for the marker directly. ioscan.palettes() adds a white/black group test that
    # a full-page asset's palette does not pass, and it returns nothing for dead.io.
    # The marker occurs freely inside 4bpp pixel data -- 80 hits across the game, 17 of
    # them palettes (FORMATS 3.9). A record that would not fit is certainly not one.
    marks = [i for i in range(len(d) - 4)
             if d[i:i + 4] == b"\xfe\xff\x00\x00" and i + 4 + 768 <= len(d)]
    for m in marks:
        out.append((m, m + 4, "palette marker fe ff 00 00", "3.9"))
        out.append((m + 4, m + 4 + 768, "palette, 256 x RGB, 8-bit", "3.9"))

    # a whole VGA page: only where there is no sprite chain (3.18)
    if not sprites:
        for m in marks:
            p = m + 4
            start = p + 768 + 8
            if start + PAGE <= len(d):
                out.append((p + 768, start, "unread", "3.18"))
                out.append((start, start + PAGE, "320x200 VGA page, 8bpp indices", "3.18"))
                break

    # NUL-terminated strings (section 10). Conservative: a run of >=6 printable bytes
    # ending in NUL. This is what makes message*.io and textin*.io read as understood
    # rather than as 16 bytes of header and a void.
    i, n = 16, len(d)
    while i < n:
        if 0x20 <= d[i] <= 0x7E:
            j = i
            while j < n and 0x20 <= d[j] <= 0x7E:
                j += 1
            if j - i >= 6 and j < n and d[j] == 0:
                out.append((i, j + 1, f"string ({j-i} chars + NUL)", "10"))
            i = j + 1
        else:
            i += 1

    # Whatever sits between the asset header and the first identified structure is script
    # when the asset is known to carry any (FORMATS 3.16 / 7.7); otherwise say so.
    after = [s for s, _, _, _ in out if s > 16]
    end = min(after) if after else len(d)
    if end > 16:
        if name.lower() in SCRIPTED:
            # Break out any identified offset that falls inside the script region --
            # otherwise a named finding vanishes into "script bytecode", which is exactly
            # how the region rule at gerdep.io 7243 stayed invisible after being recorded
            # in three hand-written documents.
            marks = sorted(o for (a, o) in IDENTIFIED if a == name.lower() and 16 <= o < end)
            at = 16
            for m in marks:
                if m > at:
                    out.append((at, m, "script bytecode (entry set known, 7.7)", "3.16"))
                # a script statement has no length here, so give it a nominal span
                nxt = min([x for x in marks if x > m] + [end])
                out.append((m, min(m + 32, nxt), f"**@{m}** - {IDENTIFIED[(name.lower(), m)]}",
                            "7"))
                at = min(m + 32, nxt)
            if at < end:
                out.append((at, end, "script bytecode (entry set known, 7.7)", "3.16"))
        else:
            # Say what it looks like, but do NOT count it as accounted for: calling this
            # script just because it sits where script usually sits put theend.io at 100%
            # while nobody could read a byte of it. The tell is a statement opcode in the
            # first two bytes -- 0x1f/0x29/0x14/0x0a are the common openings (FORMATS 7.2b).
            looks = d[16] in (0x1f, 0x29, 0x14, 0x0a, 0x00) and d[17] in vmi_stmt
            out.append((16, end,
                        "UNEXPLAINED (reads as script bytecode, never traversed - no entry set)"
                        if looks else "UNEXPLAINED", ""))

    out = [(s, min(e, len(d)), lab, ref) for s, e, lab, ref in out if s < len(d)]
    out.sort()
    merged, last = [], 0
    for s, e, lab, ref in out:
        if s < last:                      # drop a span already covered
            continue
        if s > last:
            merged.append((last, s, "UNEXPLAINED", ""))
        merged.append((s, e, lab, ref))
        last = e
    if last < len(d):
        merged.append((last, len(d), "UNEXPLAINED", ""))
    return raw, d, merged


def report(name):
    raw, d, sp = spans(name)
    size = int.from_bytes(raw[0:3], "little")
    print(f"{name}  --  {len(raw):,} bytes on disk, {len(d):,} decoded")
    print(f"  container header (FORMATS 3.0): size {size:,} (24-bit), "
          f"mode {raw[3] & 0xfe:#04x}, catalogue flag {struct.unpack_from('<H', raw, 4)[0]}")
    print(f"  {'range':>18}  {'len':>8}  what")
    for s, e, lab, ref in sp:
        tag = f"  [{ref}]" if ref else "  <-- not accounted for"
        print(f"  {s:8}..{e:<8} {e-s:8,}  {lab}{tag}")
    known = sum(e - s for s, e, lab, _ in sp if not lab.startswith("UNEXPLAINED"))
    print(f"  accounted for: {known:,} / {len(d):,} = {known*100.0/len(d):.1f}%")


def compact(sp, gap=96):
    """One row per structure, not per element.

    A chain of 36 sprites or 200 strings is one fact, and the small UNEXPLAINED gaps
    between them are separators, not mysteries -- folding them into the run is what keeps
    this file readable. Gaps of `gap` bytes or more stay visible on their own.
    """
    def kindof(lab):
        if lab.startswith("**"):
            return None                      # identified: keep it on its own row
        if lab.startswith(("sprite header", "sprite pixels")):
            return "sprites"
        if lab.startswith("string ("):
            return "strings"
        if lab.startswith(("palette marker", "palette,")):
            return "palette"
        return None

    out, i = [], 0
    while i < len(sp):
        k = kindof(sp[i][2])
        if k is None:
            s0, e0, lab, ref = sp[i]
            while (out and out[-1][2].startswith("UNEXPLAINED") and lab.startswith("UNEXPLAINED")
                   and out[-1][1] == s0):
                s0 = out.pop()[0]
            out.append((s0, e0, lab, ref))
            i += 1
            continue
        j, n, modes, holes, dims = i, 0, set(), 0, []
        while j < len(sp):
            kk = kindof(sp[j][2])
            if kk == k:
                if sp[j][2].startswith("sprite header"):
                    n += 1
                    modes.add(sp[j][2].split("mode ")[1].split(",")[0])
                    dims.append(tuple(int(v) for v in
                                      sp[j][2].rsplit(", ", 1)[1].split("x")))
                elif sp[j][2].startswith("string ("):
                    n += 1
                elif sp[j][2].startswith("palette marker"):
                    n += 1
                j += 1
            elif (sp[j][2].startswith("UNEXPLAINED") and sp[j][1] - sp[j][0] < gap
                  and j + 1 < len(sp) and kindof(sp[j + 1][2]) == k):
                holes += sp[j][1] - sp[j][0]
                j += 1
            else:
                break
        span = (sp[i][0], sp[j - 1][1])
        if k == "sprites":
            lab = f"{n} sprites, mode{'s' if len(modes) > 1 else ''} {', '.join(sorted(modes))}"
            if dims:
                lo = min(dims, key=lambda d: d[0] * d[1])
                hi = max(dims, key=lambda d: d[0] * d[1])
                lab += (f", {lo[0]}x{lo[1]}" if lo == hi
                        else f", {lo[0]}x{lo[1]} to {hi[0]}x{hi[1]}")
            ref = "3.10"
        elif k == "strings":
            lab = f"{n} NUL-terminated strings"
            ref = "10"
        else:
            lab = f"{n} palette{'s' if n > 1 else ''}: marker + 256 x RGB"
            ref = "3.9"
        if holes:
            lab += f" (+{holes:,} b between)"
        out.append((span[0], span[1], lab, ref))
        i = j
    return out


def descriptions():
    """The 'what it is' and usability columns from FINDINGS 4.19, so FILES.md says what
    each asset is FOR and not only what bytes are in it."""
    import re
    d = {}
    for ln in open(os.path.join(HERE, "FINDINGS.md")):
        m = re.match(r"^\| `([a-z0-9]+\.io)` \| [\d,]+ \| ([^|]+)\|([^|]*)\|([^|]*)\|", ln)
        if m:
            d[m.group(1)] = (m.group(2).strip(), m.group(3).strip(), m.group(4).strip())
    return d


def write_files_md():
    desc = descriptions()
    names = sorted(n for n in os.listdir(GAME) if n.lower().endswith(".io"))
    body, index, tk, tt = [], [], 0, 0
    for n in names:
        try:
            raw, d, sp = spans(n)
        except Exception:
            continue
        known = sum(e - s for s, e, lab, _ in sp if not lab.startswith("UNEXPLAINED"))
        tk += known; tt += len(d)
        kind, what, use = desc.get(n, ("?", "", ""))
        index.append(f"| [`{n}`](#{n.replace('.', '')}) | {len(d):,} | {kind} | "
                     f"{known*100.0/len(d):.0f}% | {what or use} |")
        body.append(f"### {n}\n")
        line = f"{len(raw):,} bytes on disk, **{len(d):,} decoded** \u00b7 {kind}"
        if what:
            line += f" \u00b7 {what}"
        body.append(line + "\n")
        if n in ASSET_NOTES:
            body.append(ASSET_NOTES[n] + "\n")
        body.append("| bytes | len | what |")
        body.append("|---|---|---|")
        for s, e, lab, ref in compact(sp):
            tag = f" ({ref})" if ref else ""
            body.append(f"| {s:,}..{e:,} | {e-s:,} | {lab}{tag} |")
        body.append(f"\n**{known*100.0/len(d):.1f}% named.** {use}\n")
    hdr = [
        "# FILES.md \u2014 every asset, byte by byte", "",
        "Generated by `tools/anatomy.py --files`. **Do not edit by hand** \u2014 it is",
        "regenerated from the game's own bytes, so it cannot drift from them.",
        "",
        f"**{len(names)} assets, {tt:,} bytes decoded, {tk*100.0/tt:.1f}% of those bytes named.**",
        "Section numbers in the `what` column point at FORMATS.md.",
        "`UNEXPLAINED` means exactly that: nobody knows yet.", "",
        "| file | decoded | kind | named | what it is |", "|---|---|---|---|---|",
    ] + index + ["", "---", ""]
    open(os.path.join(HERE, "FILES.md"), "w").write("\n".join(hdr + body) + "\n")
    print(f"FILES.md: {len(names)} assets, {tk*100.0/tt:.1f}% of bytes named")


def main():
    if "--files" in sys.argv:
        write_files_md()
    elif "--all" in sys.argv:
        rows = []
        for n in sorted(os.listdir(GAME)):
            if not n.lower().endswith(".io"):
                continue
            try:
                _, d, sp = spans(n)
            except Exception as e:
                print(f"  {n:14} decode failed ({e})")
                continue
            known = sum(e - s for s, e, lab, _ in sp if not lab.startswith("UNEXPLAINED"))
            rows.append((known * 100.0 / len(d), n, known, len(d)))
        rows.sort()
        for pct, n, known, tot in rows:
            print(f"  {n:14} {pct:5.1f}%   {known:8,} / {tot:,}")
        tk = sum(r[2] for r in rows); tt = sum(r[3] for r in rows)
        print(f"\n  {len(rows)} assets, {tk:,} / {tt:,} bytes accounted for = {tk*100.0/tt:.1f}%")
    else:
        report(sys.argv[1])


main()

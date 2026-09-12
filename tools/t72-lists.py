#!/usr/bin/env python3
"""Find every list of named things in a message asset, and where each one starts.

The message files store strings as `<tag> 04 <TEXT> 00` (FORMATS 3.22). Tag `0xb9` is a UI
label; tag `0x1e` is a *named thing* -- a race, a class, an item, a spell -- and the game
addresses those by index, so each run of them is a table somebody's byte points into.

Records inside one list sit a constant few bytes apart, because the bytes between them are
that list's per-entry data. A jump in that gap is a list boundary. That is the whole
heuristic, and it is why the class list came out one entry short when it was read off a
hand-picked address range instead: DARK KNIGHT looked like the end.

    tools/t72-lists.py [asset] [--min N]
"""
import os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
_src = open(os.path.join(HERE, "tools", "io.py")).read().replace("sys.exit(main())", "")
_g = {"__name__": "ishio"}
exec(compile(_src, "io.py", "exec"), _g)
decode = _g["decode"]

REC = re.compile(rb"\x1e\x04([\x20-\x7e]{2,30})\x00")

def lists(d, min_len=3):
    """Group records by the gap *between* them, not by each record's own forward gap.

    n records have n-1 gaps, and a run of k similar gaps covers k+1 records. Comparing a
    record against the previous record's forward gap instead puts each list's first entry
    at the tail of the list before it -- which is how the race list came out as four
    entries with HUMAIN filed under the line before it.
    """
    recs = [(m.start(), m.end(), m.group(1).decode()) for m in REC.finditer(d)]
    gaps = [recs[i + 1][0] - recs[i][1] for i in range(len(recs) - 1)]
    out, i = [], 0
    while i < len(gaps):
        j = i
        while j + 1 < len(gaps) and abs(gaps[j + 1] - gaps[i]) <= 2:
            j += 1
        if j - i + 2 >= min_len:
            out.append(recs[i:j + 2])
        i = j + 1
    return out

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    name = args[0] if args else "messagee.io"
    mn = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 3
    d = decode(open(os.path.join(GAME, name), "rb").read())[0]
    for grp in lists(d, mn):
        start, _, _ = grp[0]
        print(f"\n@{start} ({start:#x})  {len(grp)} entries, gap "
              f"{grp[1][0] - grp[0][1] if len(grp) > 1 else '?'}")
        for i, (s, _, txt) in enumerate(grp):
            print(f"   {i:2d}  @{s:<6} {txt}")

if __name__ == "__main__":
    main()

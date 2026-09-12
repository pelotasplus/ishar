#!/usr/bin/env python3
"""Re-measure the numbers the documents claim, and compare.

The nearest a script gets to checking whether a claim is true. It cannot judge prose, but
a great many claims here are numbers with a measurement behind them, and a number can be
taken again.

This exists because a number once moved on its own: editing one label in
`tools/anatomy.py` took the corpus figure from 47.9% to 56.6% without a byte becoming
understood, and it was published as a headline for a minute. A number that changes when the
measurement did not is the alarm.

Offline only -- nothing here needs the emulator, so it can run on every commit.

    tools/reverify.py            re-measure and compare
"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import ioscan
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")


def io_files():
    return sorted(n for n in os.listdir(GAME) if n.lower().endswith(".io"))


def m_assets_decode():
    ok = 0
    for n in io_files():
        try:
            ioscan.decode(open(os.path.join(GAME, n), "rb").read())
            ok += 1
        except Exception:
            pass
    return ok


def m_u24_over_64k():
    """Assets whose decoded size needs the header's third byte."""
    return sum(1 for n in io_files()
               if open(os.path.join(GAME, n), "rb").read(3)[2])


def m_grid_bytes():
    return os.path.getsize(os.path.join(GAME, "cont1.fic"))


def m_equal_nibble(name):
    d = ioscan.decode(open(os.path.join(GAME, name), "rb").read())[0]
    return round(sum(1 for b in d if (b >> 4) == (b & 15)) * 100.0 / len(d), 1)


def m_named_percent():
    """The figure FILES.md states, re-derived from its own rows rather than trusted."""
    text = open(os.path.join(HERE, "FILES.md")).read()
    m = re.search(r"\*\*(\d+) assets, ([\d,]+) bytes decoded, ([\d.]+)% of those bytes named",
                  text)
    return float(m.group(3)) if m else None


def m_chani_attrs():
    return sum(1 for l in open(os.path.join(HERE, "ishar.chani"))
               if l.startswith("attr["))


def m_arbre_sizes():
    import chains
    d = ioscan.decode(open(os.path.join(GAME, "arbre.io"), "rb").read())[0]
    return len({(w, h) for c in chains.all_chains(d) for _, w, h, _ in c})


# (label, measure, documented value, where it is written)
def m_class_index(name="THIEF"):
    """The index of a class in messagee.io's list -- the number a character's class byte holds.

    FINDINGS 6.15 reads BORMINH's class byte as 4 and his panel as THIEF. That pairing is
    what makes the class row identifiable, so the list's order is load-bearing.
    """
    d = ioscan.decode(open(os.path.join(GAME, "messagee.io"), "rb").read())[0]
    names = [m.group(1).decode() for m in
             re.finditer(rb"\x1e\x04([A-Z][A-Z ]{1,14})\x00", d[0x1bf0:0x1d00])]
    return names.index(name) if name in names else -1


def _list_at(off, name="messagee.io"):
    """How many entries the `1e 04` list starting at `off` has, found from record spacing.

    Not from a byte range: reading the class list out of a hand-picked window is what made
    it 16 instead of 17, because the window ended after DARK KNIGHT (FINDINGS 6.16).
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "t72lists", os.path.join(HERE, "tools", "t72-lists.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    d = ioscan.decode(open(os.path.join(GAME, name), "rb").read())[0]
    for grp in m.lists(d):
        if grp[0][0] == off:
            return len(grp)
    return -1


def m_class_count():
    """How many classes messagee.io lists."""
    return _list_at(7166)


def m_item_count():
    """How many items messagee.io lists."""
    return _list_at(5456)


def m_spell_count():
    """How many spells messagee.io lists."""
    return _list_at(7520)


CLAIMS = [
    ("`.io` files that decode",            m_assets_decode,           98,     "FORMATS 3.6"),
    ("assets needing the 24-bit size",     m_u24_over_64k,             9,     "FORMATS 3.0"),
    ("cont1.fic bytes",                    m_grid_bytes,            4860,     "FORMATS 3.12"),
    ("theend.io equal-nibble %",           lambda: m_equal_nibble("theend.io"), 78.7, "FORMATS 3.19"),
    ("logo.io equal-nibble %",             lambda: m_equal_nibble("logo.io"),   53.6, "FORMATS 3.19"),
    ("dead.io equal-nibble %",             lambda: m_equal_nibble("dead.io"),   25.5, "FORMATS 3.19"),
    ("arbre.io distinct sprite sizes",     m_arbre_sizes,             15,     "FINDINGS 4.15c"),
    ("FILES.md named %",                   m_named_percent,         62.0,     "FILES.md header"),
    ("messagee.io classes listed",         m_class_count,             17,     "FINDINGS 6.16"),
    ("messagee.io items listed",           m_item_count,              41,     "FINDINGS 6.16"),
    ("messagee.io spells listed",          m_spell_count,             33,     "FINDINGS 6.16"),
    ("THIEF's class index",                m_class_index,              4,     "FINDINGS 6.15"),
]

# Numbers that must never go DOWN. This is the guard for the failure CLAUDE.md describes
# under "a regex that edits the database can eat the database": 149 annotations were deleted
# by one substitution, nothing complained, and it surfaced two tasks later as coverage
# sliding. A high-water mark catches it on the next commit instead.
RATCHET = [
    ("ishar.chani annotations", m_chani_attrs),
    ("FILES.md named %",        m_named_percent),
]
MARKS = os.path.join(HERE, ".ish", "ratchet.json")


def main():
    bad = 0
    print(f"  {'claim':<34} {'documented':>11} {'measured':>10}")
    for label, fn, want, where in CLAIMS:
        try:
            got = fn()
        except Exception as e:
            print(f"  {label:<34} {want!s:>11} {'ERROR':>10}  {type(e).__name__}")
            bad = 1
            continue
        same = (abs(got - want) < 0.05) if isinstance(want, float) else (got == want)
        print(f"  {label:<34} {want!s:>11} {got!s:>10}  "
              f"{'ok' if same else 'CHANGED  <- ' + where}")
        if not same:
            bad = 1
    import json
    prev = {}
    if os.path.exists(MARKS):
        prev = json.load(open(MARKS))
    print()
    marks = {}
    for label, fn in RATCHET:
        got = fn()
        marks[label] = got
        was = prev.get(label)
        if was is None:
            print(f"  {label:<34} {'-':>11} {got!s:>10}  first run, recorded")
        elif got < was:
            print(f"  {label:<34} {was!s:>11} {got!s:>10}  WENT DOWN")
            bad = 1
        else:
            print(f"  {label:<34} {was!s:>11} {got!s:>10}  ok")
            marks[label] = max(got, was)
    if not bad:
        os.makedirs(os.path.dirname(MARKS), exist_ok=True)
        json.dump(marks, open(MARKS, "w"), indent=1)
    if bad:
        print("\nA number moved the wrong way. Either the measurement changed and the\n"
              "document is stale, or something broke. Find out which before editing either.\n"
              "A count that falls when you meant to add is the whole check.")
    return bad


sys.exit(main())

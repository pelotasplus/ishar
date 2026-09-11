#!/usr/bin/env python3
"""Find a script's entry points statically, for assets never seen executing.

t37f-poll.py gets entries by catching DS:SI at vm_run, which only works for scripts
that actually run. Three known-script assets (monstre.io, telep.io, dead.io) never do.

Method: traverse from every offset that could start a statement, keep the ones whose
region closes cleanly (no rejected branch target, no unknown statement), then pick a
minimal covering set. A real entry's region closes; a mid-data offset's does not.
"""
import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import vmi

def scan(name, minstmt=3):
    d = vmi.decode(open(os.path.join(vmi.GAME, name), "rb").read())[0]
    good = {}
    for p in range(len(d)):
        if not vmi.plausible(d, p):
            continue
        seen, cov, unk = vmi.traverse(d, p)
        if vmi.traverse.rejected or unk or len(seen) < minstmt:
            continue
        good[p] = seen
    picked, covered = [], set()
    for p in sorted(good, key=lambda p: (-len(good[p]), p)):
        if good[p] - covered:
            picked.append(p)
            covered |= good[p]
    # an entry reached from another pick is that pick's interior, not an entry
    roots = [p for p in sorted(picked)
             if not any(p in good[q] for q in picked if q != p and p in good[q])]
    return d, good, roots, covered

for name in sys.argv[1:]:
    d, good, roots, covered = scan(name)
    seen, cov, unk = vmi.traverse_all(d, roots)
    print(f"{name}: {len(d)} bytes, {len(good)} clean starts, {len(roots)} roots -> "
          f"{len(seen)} statements, {cov} code bytes ({cov*100.0/len(d):.1f}%), {len(unk)} unknown")
    print(f"  roots: {roots[:30]}")

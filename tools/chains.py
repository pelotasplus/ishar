#!/usr/bin/env python3
"""Find ALL sprite chains in an asset, not just the best-scoring one.

tools/ioscan.py picks the single offset whose chain explains the most of the file. frise.io
has two: 14 sprites at 35964 and three more at 51456, 8,942 bytes apart -- and the second
chain is the one that actually draws the right-hand panel (T53). Everything in the gap, and
every later chain, was invisible.
"""
import os, struct, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import ioscan
from ioscan import decode, rec
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")

def walk(d, start, taken):
    out, off = [], start
    while off not in taken:
        r = rec(d, off)
        if not r:
            break
        n, w, h = r
        out.append((off, w, h, n))
        off += n
    return out

def all_chains(d, minlen=2):
    taken, chains = set(), []
    while True:
        best = None
        for off in range(0, len(d) - 8, 2):
            if off in taken:
                continue
            c = walk(d, off, taken)
            if len(c) >= minlen and (best is None or
                                     sum(x[3] for x in c) > sum(x[3] for x in best)):
                best = c
        if not best:
            break
        chains.append(best)
        for o, w, h, n in best:
            taken.update(range(o, o + n))
    return chains

def main():
    names = sys.argv[1:]
    if not names or names == ["--all"]:
        names = sorted(n for n in os.listdir(GAME) if n.lower().endswith(".io"))
    tot_one = tot_all = tot_len = 0
    for n in names:
        try:
            d = decode(open(os.path.join(GAME, n), "rb").read())[0]
        except Exception:
            continue
        cs = all_chains(d)
        one = max((sum(x[3] for x in c) for c in cs), default=0)
        every = sum(sum(x[3] for x in c) for c in cs)
        tot_one += one; tot_all += every; tot_len += len(d)
        if len(names) == 1:
            print(f"{n}: {len(cs)} chains, {every:,} / {len(d):,} bytes")
            for c in cs:
                print(f"  {len(c):3} sprites at {c[0][0]:6}..{c[-1][0]+c[-1][3]:<6} "
                      f"{sum(x[3] for x in c):7,} bytes")
        elif len(cs) > 1:
            print(f"  {n:14} {len(cs)} chains  best {one*100.0/len(d):5.1f}%  "
                  f"all {every*100.0/len(d):5.1f}%")
    if len(names) > 1:
        print(f"\n{len(names)} assets: best chain only {tot_one*100.0/tot_len:.1f}%, "
              f"all chains {tot_all*100.0/tot_len:.1f}% of {tot_len:,} bytes")

main()

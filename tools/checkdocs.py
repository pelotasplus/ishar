#!/usr/bin/env python3
"""Does every asset offset named in the prose reach FILES.md?

FILES.md is generated, so a finding written into FINDINGS.md or FORMATS.md does not appear
there unless IDENTIFIED in tools/anatomy.py is edited too. That was forgotten three times
in one session, each time noticed by the user rather than by anything here.

This greps the prose for `name.io` @NNNN / "name.io offset NNNN" and reports any that
IDENTIFIED does not carry. Exit code 1 if there are any, so it can gate a commit.
"""
import os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))

PAT = re.compile(r"`?([a-z0-9]+\.io)`?\s*(?:@|offset\s+)(\d{3,6})")

def identified():
    src = open(os.path.join(HERE, "tools", "anatomy.py")).read()
    block = src.split("IDENTIFIED = {", 1)[1].split("\n}", 1)[0]
    return {(m.group(1), int(m.group(2)))
            for m in re.finditer(r'\("([a-z0-9.]+)",\s*(\d+)\)', block)}

def main():
    known = identified()
    missing = {}
    for doc in ("FINDINGS.md", "FORMATS.md", "REBUILD.md"):
        path = os.path.join(HERE, doc)
        if not os.path.exists(path):
            continue
        for n, line in enumerate(open(path), 1):
            for m in PAT.finditer(line):
                key = (m.group(1).lower(), int(m.group(2)))
                if key not in known:
                    missing.setdefault(key, []).append(f"{doc}:{n}")
    if not missing:
        print(f"ok: every asset offset in the prose is in IDENTIFIED ({len(known)} entries)")
        return 0
    print(f"{len(missing)} asset offsets named in prose but missing from "
          f"IDENTIFIED in tools/anatomy.py:")
    for (asset, off), where in sorted(missing.items()):
        print(f"  {asset} @{off}   {', '.join(where[:3])}")
    print("\nAdd them, then: python3 tools/anatomy.py --files")
    return 1

sys.exit(main())

#!/usr/bin/env python3
"""Every identifier named in the prose must exist where it is supposed to live.

The prose documents are written by hand; the durable artefacts are not. A finding that
names something and never reaches its artefact is invisible to the next reader, and every
such failure here has been silent -- no error, no warning, no number moving.

The first version of this script checked one kind of reference, because it was written in
response to one failure. Code addresses then went missing from `ishar.chani` the same way.
So RULES is a table: adding a kind of reference is one entry, not a new script.

    tools/checkdocs.py            report, exit 1 if anything is stranded
"""
import os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = ("FINDINGS.md", "FORMATS.md", "REBUILD.md")


def identified():
    """(asset, offset) pairs in IDENTIFIED in tools/anatomy.py."""
    src = open(os.path.join(HERE, "tools", "anatomy.py")).read()
    block = src.split("IDENTIFIED = {", 1)[1].split("\n}", 1)[0]
    return {(m.group(1).lower(), int(m.group(2)))
            for m in re.finditer(r'\("([a-z0-9.]+)",\s*(\d+)\)', block)}


# Identifiers named in prose that deliberately do not resolve, each with its reason. A gate
# that cannot be satisfied gets bypassed, so anything genuinely unresolvable belongs here
# rather than in a permanent failure. Keyed by rule label prefix.
ALLOW = {
    "T36": "renumbered away (ROADMAP:1049); references are to the closed "
           "corpus-verification task",
    "seg_0000:0022": "the four spare `ret` bytes below the dispatch tables, not a routine",
    "seg_0000:038b": "quoted as a mislabelling; the real routine is seg_0e97:038b",
    "seg_13d7:03a6": "chani panics on code seeds here (CLAUDE.md); dropped-seed list",
    "seg_13d7:0402": "chani panics on code seeds here",
    "seg_13d7:048a": "chani panics on code seeds here",
    "seg_13d7:0574": "chani panics on code seeds here",
    "seg_13d7:05fc": "chani panics on code seeds here",
    "seg_13d7:066a": "chani panics on code seeds here",
    "seg_13d7:0b8e": "chani panics on code seeds here",
    "seg_13d7:0b90": "chani panics on code seeds here",
}


def annotated(reach=96):
    """Addresses an annotation covers.

    A reference usually points *inside* a named routine -- seg_0e97:0597 is in the loop
    annotated at 0568 -- so demanding its own attr[] would be wrong and would make the gate
    unsatisfiable. An address counts as covered when an annotation in the same segment sits
    within `reach` bytes before it.
    """
    attrs = {}
    for m in re.finditer(r"^attr\[(seg_[0-9a-f]{4}):([0-9a-f]{4})\]",
                         open(os.path.join(HERE, "ishar.chani")).read(), re.M):
        attrs.setdefault(m.group(1), set()).add(int(m.group(2), 16))

    class Covered:
        def __contains__(self, addr):
            seg, _, off = addr.partition(":")
            off = int(off, 16)
            near = [a for a in attrs.get(seg, ()) if 0 <= off - a <= reach]
            return bool(near)
        def __len__(self):
            return sum(len(v) for v in attrs.values())
    return Covered()


def captures_on_disk():
    d = os.path.join(HERE, "captures")
    out = set()
    for root, _, files in os.walk(d):
        rel = os.path.relpath(root, HERE)
        for f in files:
            out.add(os.path.join(rel, f).replace(os.sep, "/"))
    return out


def roadmap_tasks():
    return {m.group(1) for m in
            re.finditer(r"\*\*(T\d+[a-z0-9]*)\s*\u00b7",
                        open(os.path.join(HERE, "ROADMAP.md")).read())}


def tools_listed():
    return {m.group(1) for m in
            re.finditer(r"`tools/([A-Za-z0-9_.-]+)`",
                        open(os.path.join(HERE, "TOOLS.md")).read())}


# (label, pattern, key from match, set of things that exist, how to fix)
RULES = [
    ("asset offset -> IDENTIFIED in tools/anatomy.py",
     re.compile(r"`?([a-z0-9]+\.io)`?\s*(?:@|offset\s+)(\d{3,6})"),
     lambda m: (m.group(1).lower(), int(m.group(2))),
     identified,
     "add it to IDENTIFIED, then: python3 tools/anatomy.py --files"),

    ("code address -> attr[] in ishar.chani",
     re.compile(r"`(seg_[0-9a-f]{4}:[0-9a-f]{4})`"),
     lambda m: m.group(1),
     annotated,
     "annotate it in ishar.chani, then: tools/disasm.sh"),

    ("tool -> TOOLS.md",
     re.compile(r"`tools/([A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:py|sh))`"),
     lambda m: m.group(1),
     tools_listed,
     "give it a docstring, then: python3 tools/toolsindex.py"),

    ("capture -> a file in captures/",
     re.compile(r"`(captures/[A-Za-z0-9_./-]+\.png)`"),
     lambda m: m.group(1),
     captures_on_disk,
     "take the screenshot with `tools/ish shot NAME`, or fix the reference"),

    ("task id -> an entry in ROADMAP.md",
     re.compile(r"\b(T\d+[a-z0-9]*)\b"),
     lambda m: m.group(1),
     roadmap_tasks,
     "file the task in ROADMAP.md, or fix the reference"),
]

# What this script does NOT check, stated so the gate's coverage is visible rather than
# assumed. Every line here is a place a finding can still go missing silently -- which is
# how 25 stranded addresses accumulated while an earlier version of this file passed.
BLIND_SPOTS = [
    "whether a claim is TRUE -- only a measurement does that",
    "whether a section carries an Evidence: or Verified by: line",
    "whether a struck or superseded claim has reappeared unstruck elsewhere",
    "whether a number in the prose still matches what its tool prints",
    "whether an IDENTIFIED entry is actually VISIBLE in FILES.md, or collapsed into a span",
    "anything in ROADMAP.md, CLAUDE.md or the skills",
]


def main():
    bad = 0
    for label, pat, key, existing, fix in RULES:
        have = existing()
        missing = {}
        for doc in DOCS:
            path = os.path.join(HERE, doc)
            if not os.path.exists(path):
                continue
            for n, line in enumerate(open(path), 1):
                if line.lstrip().startswith("~~"):     # struck text, deliberately stale
                    continue
                for m in pat.finditer(line):
                    k = key(m)
                    if k in ALLOW:
                        continue
                    if k not in have:
                        missing.setdefault(k, []).append(f"{doc}:{n}")
        if missing:
            bad = 1
            print(f"{len(missing)} stranded -- {label}:")
            for k, where in sorted(missing.items(), key=lambda kv: str(kv[0])):
                print(f"  {k}   {', '.join(where[:3])}")
            print(f"  fix: {fix}\n")
        else:
            print(f"ok ({len(have)} known) -- {label}")
    print("\nnot checked by this script:")
    for b in BLIND_SPOTS:
        print(f"  - {b}")
    return bad


sys.exit(main())

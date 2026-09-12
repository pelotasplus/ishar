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

# Sections written before the Evidence discipline existed. Listed rather than tolerated:
# the gate stays green, the debt stays visible, and T57 works through it. Do NOT add to
# this -- a new section without evidence is the failure this check is for.
EVIDENCE_DEBT = {
    ("FINDINGS.md", "1.2 Combat"), ("FINDINGS.md", "1.3 Magic"),
    ("FINDINGS.md", "2.2 Mouse"),
    ("FORMATS.md", "1.1 MZ header (packed)"),
    ("FORMATS.md", "1.2 Entry stub (image `+0x0003`)"),
    ("FORMATS.md", "1.3 Compression \u2014 LZEXE-family bit-stream LZ"),
    ("FORMATS.md", "1.4 Relocation table"),
    ("FORMATS.md", "3.1 How the game reads one"),
    ("FORMATS.md", "8.1 The file on disk (730 bytes)"),
    ("FORMATS.md", "8.2 The 1432 decoded bytes"),
    ("FORMATS.md", "9.1 The file on disk (7,868 bytes)"),
    ("FORMATS.md", "9.2 The decoded 11,272 bytes"),
    ("FORMATS.md", "9.3 Writing a reader"),
    ("FORMATS.md", "9.6 The spec, validated by an independent implementation"),
    ("FORMATS.md", "10.2 All four variants share one asset id"),
    ("FORMATS.md", "10.3 The string encoding"),
    ("FORMATS.md", "10.5 How much of these files the strings explain: 8-12%"),
}


def sections_without_evidence():
    """Sections in FINDINGS/FORMATS carrying no Evidence:, Verified by: or Status line.

    This is the check that would have caught the shear: FORMATS 3.13d had a Verified-by
    line covering how the routines were FOUND, while the sentence interpreting the two
    numbers was invented -- but a section with no line at all is the easier failure, and it
    was never measured.
    """
    out = []
    for doc in ("FINDINGS.md", "FORMATS.md"):
        path = os.path.join(HERE, doc)
        if not os.path.exists(path):
            continue
        head, body, line_no = None, [], 0
        def flush():
            if head and (doc, head) not in EVIDENCE_DEBT and not any(
                    k in "".join(body) for k in
                    ("Evidence:", "Verified by:", "Status:", "**Status**", "unresolved",
                     "Not known", "not established", "Not established")):
                out.append((doc, line_no, head))
        for n, line in enumerate(open(path), 1):
            # Only numbered sections carry findings. Prose subsections like "Ground truth"
            # or "Control flow" belong to the numbered one above them and share its
            # evidence line.
            if line.startswith("### ") and re.match(r"### \d+\.\d", line):
                flush()
                head, body, line_no = line.strip()[4:], [], n
            elif line.startswith("### "):
                flush()
                head, body, line_no = None, [], n
            elif head:
                body.append(line)
        flush()
    return out


def identified_visible():
    """IDENTIFIED entries whose text does not appear in FILES.md.

    Adding to IDENTIFIED is necessary and was twice not sufficient: the generator collapsed
    a sprite chain and then a script region, swallowing the entry both times. Checking the
    entry exists proved nothing; checking it is VISIBLE is the real test.
    """
    files_md = os.path.join(HERE, "FILES.md")
    if not os.path.exists(files_md):
        return []
    text = open(files_md).read()
    src = open(os.path.join(HERE, "tools", "anatomy.py")).read()
    block = src.split("IDENTIFIED = {", 1)[1].split("\n}", 1)[0]
    out = []
    for m in re.finditer(r'\("([a-z0-9.]+)",\s*(\d+)\):', block):
        asset, off = m.group(1), int(m.group(2))
        # FILES.md renders offsets with thousands separators
        if f"**@{off}**" in text or f"{off:,}.." in text:
            continue
        out.append((asset, off))
    return out


# Claims this project measured, then disproved. Each was believed, written down, and acted
# on; several were then read back out of the docs and repeated. A retracted claim is only
# retracted if it stops appearing as a claim, so this fails if one shows up on a line that
# is not marking it as wrong.
STRUCK = {
    "intro is minutes long": "the intro is ~3 screens; the frozen frame was a fault",
    "one pixel sideways": "cs:[002e] is 320 + pixels drawn, not a shear (T54)",
    "crash is the sound driver": "the next --audio none run faulted too",
    "group = word0 >> 8": "the palette group is in word 3 (T11r)",
    "4bpp sprites are opaque": "modes 0x00 and 0x10 key nibble 0 (3.13c)",
    "never raises IRQ12": "the mouse device was wired to the GUI; fixed in T29c3",
    "does not use the mouse": "it installs an INT 33h handler at startup",
    "too small for the demon frame": "dead.io is 65,984 bytes, not 448 (T48)",
    "vm_op_attack_swing": "renamed vm_op_15; it occurs 8x in affobj.io",
    "Dragonia": "the starting region is FRAGONIR",
    "never been observed drawn": "arbre.io was caught drawn at (13,28)",
    "no asset matches": "viewport sprites do appear verbatim; three matched at 100%",
}

# A line that is marking a claim as wrong, rather than making it.
RETRACTING = ("~~", "struck", "Struck", "superseded", "Superseded", "was wrong",
              "correct", "Correct", "Historical", "retract", "no longer",
              "previously", "used to", "disprove", "wrongly", "mislabell", "not true",
              "STRUCK", "made `", "look \"", "written up here as", "believed",
              "misreading", "half struck", "turned out", "renam", "Renam", "at first")


def struck_claims_reappearing(window=12):
    """A retraction is usually a paragraph or a heading away from the claim it retracts.

    Checking line by line produced eleven false positives out of twelve -- "Superseded
    reasoning follows" sits above the passage, not inside every line of it. So a claim is
    treated as retracted when a marker appears within `window` lines either side.
    """
    out = []
    for doc in DOCS + ("ROADMAP.md",):
        path = os.path.join(HERE, doc)
        if not os.path.exists(path):
            continue
        lines = open(path).read().split("\n")
        for i, line in enumerate(lines):
            near = "".join(lines[max(0, i - window):i + window])
            if any(w in near for w in RETRACTING):
                continue
            for phrase, why in STRUCK.items():
                if phrase in line:
                    out.append((doc, i + 1, phrase, why))
    return out


def evidence_names_something_real():
    """An Evidence/Verified-by line should cite a tool or a capture that exists.

    This is the nearest a script gets to checking whether a claim is true: not the claim,
    but whether anyone could re-check it. A citation naming a tool that does not exist is
    the shape a fabricated one takes.
    """
    tools = {f for f in os.listdir(os.path.join(HERE, "tools"))}
    caps = captures_on_disk()
    out = []
    for doc in DOCS:
        path = os.path.join(HERE, doc)
        if not os.path.exists(path):
            continue
        for n, line in enumerate(open(path), 1):
            if not re.search(r"\*\*(Evidence:|Verified by:)\*\*", line):
                continue
            for m in re.finditer(r"`tools/([A-Za-z0-9_.-]+)`", line):
                if m.group(1) not in tools:
                    out.append((doc, n, f"tools/{m.group(1)}"))
            for m in re.finditer(r"`(captures/[A-Za-z0-9_./-]+)`", line):
                ref = m.group(1)
                if ref.endswith("/"):          # a directory is a fair citation
                    if os.path.isdir(os.path.join(HERE, ref)):
                        continue
                elif ref in caps:
                    continue
                out.append((doc, n, ref))
    return out


# What this script does NOT check, stated so the gate's coverage is visible rather than
# assumed. Every line here is a place a finding can still go missing silently -- which is
# how 25 stranded addresses accumulated while an earlier version of this file passed.
BLIND_SPOTS = [
    "whether a claim is TRUE -- checked only as far as `tools/reverify.py` reaches",
    "anything in CLAUDE.md or the skills",
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
    gaps = sections_without_evidence()
    if gaps:
        bad = 1
        print(f"{len(gaps)} sections with no Evidence:, Verified by: or Status line:")
        for doc, n, head in gaps:
            print(f"  {doc}:{n}  {head[:72]}")
        print("  fix: add the line, or say what is not established\n")
    else:
        print("ok -- every section carries evidence")

    hidden = identified_visible()
    if hidden:
        bad = 1
        print(f"{len(hidden)} IDENTIFIED entries not visible in FILES.md:")
        for asset, off in hidden:
            print(f"  {asset} @{off}")
        print("  fix: the generator is collapsing the span; "
              "run python3 tools/anatomy.py --files and check\n")
    else:
        print("ok -- every IDENTIFIED entry is visible in FILES.md")

    back = struck_claims_reappearing()
    if back:
        bad = 1
        print(f"{len(back)} disproved claims stated as fact again:")
        for doc, n, phrase, why in back:
            print(f"  {doc}:{n}  \"{phrase}\" -- {why}")
        print("  fix: strike it, or say it was believed and why it was wrong\n")
    else:
        print(f"ok ({len(STRUCK)} tracked) -- no disproved claim restated as fact")

    fake = evidence_names_something_real()
    if fake:
        bad = 1
        print(f"{len(fake)} Evidence lines citing something that does not exist:")
        for doc, n, what in fake:
            print(f"  {doc}:{n}  {what}")
        print("  fix: cite what actually exists, or say the evidence is not recorded\n")
    else:
        print("ok -- every Evidence line cites a tool or capture that exists")

    print("\nnot checked by this script:")
    for b in BLIND_SPOTS:
        print(f"  - {b}")
    return bad


sys.exit(main())

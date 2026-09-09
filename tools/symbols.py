#!/usr/bin/env python3
"""
Import the functions Spice86 actually executed into ishar.chani as code seeds.

The emulator knows what ran; the relocation table only knows what is called far.
Everything the game reached through a near call or an indirect jump is invisible
to tools/segmap.py and visible here, which is where most of the coverage is.

    tools/symbols.py                 # from a running emulator, merge and report
    tools/symbols.py --dry-run       # show what would be added
    tools/symbols.py --json f.json   # from a saved list_functions response

Seeds that make chani panic (layout.rs:361, see ishar.chani) are dropped and
named, not silently skipped: a seed that vanishes without a word is a routine
nobody will think to look for again.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "ishar.chani")
DISASM = os.path.join(os.environ.get("CHANI_HOME",
                      os.path.expanduser("~/Workspace/pelotasplus/dune/chani-rs")),
                      "target", "release", "disasm")
MARK = "// ---- executed functions, imported by tools/symbols.py ----"


def emulator():
    ps = subprocess.run(["ps", "-eo", "command="], capture_output=True, text=True).stdout
    for line in ps.splitlines():
        if "ishar_legend" in line and "--McpHttpPort" in line:
            return line.split("--McpHttpPort")[1].split()[0]
    sys.exit("symbols: no running emulator (start one with ./run.sh), or use --json")


def mcp(port, tool, args):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/mcp", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode()
    for ln in raw.splitlines():
        if ln.startswith("data:"):
            r = json.loads(ln[5:].strip())["result"]
            if r.get("isError"):
                sys.exit(f"symbols: {tool} failed: {json.dumps(r)[:200]}")
            return r["structuredContent"]
    sys.exit(f"symbols: no response to {tool}")


def segments():
    text = open(DB).read()
    return [(m.group(1), int(m.group(2), 16), int(m.group(3), 16))
            for m in re.finditer(r"segment\[(seg_\w+)\]:.*?load\s*=\s*\[0\.\.\]:"
                                 r"exe\[0x([0-9a-f]+)\.\.0x([0-9a-f]+)\]", text, re.S)]


def coverage():
    r = subprocess.run([os.path.join(HERE, "tools", "disasm.sh")],
                       capture_output=True, text=True, cwd=HERE)
    return (r.stdout or r.stderr).strip()


def renders(body):
    """Does the database still build with this block appended?"""
    open(os.path.join(HERE, "_merge.chani"), "w").write(body)
    r = subprocess.run([DISASM, "_merge.chani"], capture_output=True, text=True, cwd=HERE)
    if "No such file" in (r.stderr or ""):
        sys.exit("symbols: probe misconfigured -- " + r.stderr[:120])
    return r.returncode == 0


def main():
    if "--json" in sys.argv:
        data = json.load(open(sys.argv[sys.argv.index("--json") + 1]))["result"]["structuredContent"]
        load = int(sys.argv[sys.argv.index("--load") + 1], 16) if "--load" in sys.argv else 0x017D
    else:
        port = emulator()
        data = mcp(port, "list_functions", {"limit": 5000})
        load = mcp(port, "read_dos_program_state", {})["CurrentProgramSegmentPrefix"] + 0x10
    funcs = data["Functions"] if isinstance(data, dict) and "Functions" in data else data
    segs = segments()
    if not segs:
        sys.exit("symbols: no segments in ishar.chani")
    image_end = max(e for _, _, e in segs)

    db_text = open(DB).read()
    existing = set(re.findall(r"attr\[(seg_[0-9a-f]{4}:[0-9a-f]{4})\]", db_text))
    # Seeds already imported by an earlier run. They are kept and merged with:
    # rewriting the block from just this run's list silently deletes whatever a
    # previous run found, and the coverage number goes DOWN without saying why.
    imported = set(re.findall(r"attr\[(seg_[0-9a-f]{4}:[0-9a-f]{4})\]: type = code",
                              db_text.split(MARK)[1] if MARK in db_text else ""))
    wanted, outside = {}, 0
    for f in funcs:
        linear = f["Address"]["Linear"] - load * 16
        if not 0 <= linear < image_end:
            outside += 1
            continue
        for name, start, end in segs:
            if start <= linear < end:
                key = f"{name}:{linear - start:04x}"
                wanted[key] = max(wanted.get(key, 0), f.get("CalledCount", 0))
                break
    hand_written = existing - imported
    new = sorted((set(wanted) | imported) - hand_written)
    print(f"{len(funcs)} functions, {outside} outside the image, {len(wanted)} inside; "
          f"{len(imported)} already imported, {len(new)} seeds after merging")
    if "--dry-run" in sys.argv:
        for k in new:
            print(f"  attr[{k}]: type = code    // {wanted.get(k, 0)} calls")
        return 0

    before = coverage()
    base = open(DB).read().split(MARK)[0].rstrip()
    base = base[:base.rfind("\nend")] if base.rstrip().endswith("end") else base

    def block(keys):
        lines = [MARK] + [f"attr[{k}]: type = code" for k in keys]
        return base + "\n\n" + "\n".join(lines) + "\n\nend\n"

    keep, dropped = [], []
    chunk = list(new)
    # Add in one go if it builds; otherwise fall back to one at a time so a
    # single bad seed cannot take the rest of the import with it.
    if renders(block(chunk)):
        keep = chunk
    else:
        for k in chunk:
            if renders(block(keep + [k])):
                keep.append(k)
            else:
                dropped.append(k)
    open(DB, "w").write(block(keep))
    os.remove(os.path.join(HERE, "_merge.chani"))
    print(f"imported {len(keep)} seeds, dropped {len(dropped)} that chani cannot lay out")
    for d in dropped:
        print(f"  dropped {d}  ({wanted.get(d, 0)} calls)")
    print("before:" + before[before.find("\n"):])
    after = coverage()
    print("after: " + after[after.find("\n"):])
    return 0


sys.exit(main())

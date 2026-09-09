#!/usr/bin/env python3
"""
Convert between the addresses Spice86 shows and the addresses the listing uses.

The unpacked image is loaded as one block at `load`, and ishar.chani names each
segment by its paragraph offset into that image -- so a runtime CS is
`load + <segment name>`. Doing that subtraction in your head is how a finding
ends up filed against the wrong routine.

    tools/addr.py 0abe:3f3a --load 017d      runtime  -> listing
    tools/addr.py seg_0941:3f3a --load 017d  listing  -> runtime
    tools/addr.py 0abe:3f3a                  load taken from a running emulator

`load` is stable at 017d in every run measured so far, but it is a property of
the DOS memory map, not of the file -- so it is read, not assumed.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def segments():
    """(name, start, end) for each code segment, read out of ishar.chani."""
    text = open(os.path.join(HERE, "ishar.chani")).read()
    segs = [(m.group(1), int(m.group(2), 16), int(m.group(3), 16))
            for m in re.finditer(r"segment\[(seg_\w+)\]:.*?load\s*=\s*\[0\.\.\]:"
                                 r"exe\[0x([0-9a-f]+)\.\.0x([0-9a-f]+)\]", text, re.S)]
    if not segs:
        sys.exit("addr: no segments in ishar.chani")
    return segs


def running_load():
    ps = subprocess.run(["ps", "-eo", "command="], capture_output=True, text=True).stdout
    for line in ps.splitlines():
        if "ishar_legend" in line and "--McpHttpPort" in line:
            port = line.split("--McpHttpPort")[1].split()[0]
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "read_dos_program_state",
                                          "arguments": {}}}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/mcp", data=body, method="POST",
                headers={"Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream"})
            try:
                raw = urllib.request.urlopen(req, timeout=10).read().decode()
            except Exception:
                continue
            for ln in raw.splitlines():
                if ln.startswith("data:"):
                    d = json.loads(ln[5:].strip())
                    psp = d["result"]["structuredContent"]["CurrentProgramSegmentPrefix"]
                    return psp + 0x10, f"read from the emulator on port {port}"
    sys.exit("addr: no running emulator to read `load` from -- pass --load")


def main():
    args = [a for a in sys.argv[1:] if a != "--load"]
    if "--load" in sys.argv:
        load = int(sys.argv[sys.argv.index("--load") + 1], 16)
        args = [a for a in args if a != f"{load:04x}" and a != f"{load:x}"]
        how = "given"
    else:
        load, how = running_load()
    if not args:
        sys.exit(__doc__)
    what = args[0]

    segs = segments()
    m = re.fullmatch(r"(seg_[0-9a-f]{4}):([0-9a-f]{1,4})", what, re.I)
    if m:
        name, off = m.group(1).lower(), int(m.group(2), 16)
        for n, start, _end in segs:
            if n == name:
                linear = start + off
                cs = load + (linear >> 4)
                print(f"{name}:{off:04x}  ->  runtime {cs:04x}:{linear & 0xF:04x}"
                      f"   image {linear:#07x}   (load {load:04x}, {how})")
                return
        sys.exit(f"addr: no segment {name} in ishar.chani")

    m = re.fullmatch(r"([0-9a-f]{1,4}):([0-9a-f]{1,4})", what, re.I)
    if not m:
        sys.exit(f"addr: cannot parse {what!r}")
    cs, ip = int(m.group(1), 16), int(m.group(2), 16)
    if cs < load:
        sys.exit(f"addr: CS {cs:04x} is below load {load:04x} -- not in the image")
    linear = (cs - load) * 16 + ip
    for name, start, end in segs:
        if start <= linear < end:
            print(f"{cs:04x}:{ip:04x}  ->  {name}:{linear - start:04x}"
                  f"   image {linear:#07x}   (load {load:04x}, {how})")
            return
    sys.exit(f"addr: image offset {linear:#x} is outside every declared segment "
             f"(image is {segs[-1][2]:#x} bytes)")


main()

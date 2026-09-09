#!/usr/bin/env python3
"""
Check tools/unpack.py against the emulator, byte for byte.

Runs the SHIPPED start.exe under Spice86, stops twice -- once where the
decompressor finishes, to read the end pointer it produced, and once at the
real entry the stub hands control to -- and compares the memory it decompressed
with the image unpack.py produced. Relocations are applied to our copy first,
because the stub biases them by the load segment and a file cannot be.

The length check is not decoration. A decoder that stops early produces an
image that still starts with a correct program and still disassembles as one;
comparing only the bytes we produced would pass on it.

    tools/verify-unpack.py [--port N]
"""
import json
import os
import struct
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
PACKED = os.path.join(GAME, "start.exe")
UNPACKED = os.path.join(GAME, "start-unpacked.exe")
SPICE86 = os.environ.get("SPICE86_HOME", os.path.join(os.path.dirname(HERE), "Spice86"))
DLL = os.path.join(SPICE86, "src", "Spice86", "bin", "Debug", "net10.0", "Spice86.dll")

# Image offsets of the two stopping points, from stub.chani. Both live in the
# copy, which sits 0xb640 bytes above the load address.
COPY = 0xB640
RELOCATE = 0xA8A3
ENTRY_IP = 0x25E5

PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8188
_id = [0]


def mcp(tool, args=None, timeout=60):
    _id[0] += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _id[0], "method": "tools/call",
                       "params": {"name": tool, "arguments": args or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}/mcp", data=body, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json, text/event-stream"})
    raw = urllib.request.urlopen(r, timeout=timeout).read().decode()
    p = None
    for ln in raw.splitlines():
        if ln.startswith("data:"):
            p = json.loads(ln[5:].strip())
    if p is None:
        p = json.loads(raw)
    if "error" in p:
        sys.exit(f"{tool}: {p['error']}")
    return p.get("result", {}).get("structuredContent", {})


def read_block(seg, ofs, n):
    """Walks the SEGMENT, not just the offset: the image is 86 KB and
    advancing only `ofs` runs off the end of a 64 KB segment."""
    out = bytearray()
    while n > 0:
        take = min(n, 4096)
        d = mcp("read_memory", {"segment": seg, "offset": ofs, "length": take})
        got = bytes.fromhex(d.get("Data", ""))
        if len(got) != take:
            sys.exit(f"short read at {seg:04x}:{ofs:04x}: asked {take}, got {len(got)}")
        out += got
        ofs += take
        n -= take
        if ofs >= 0x1000:
            seg += ofs >> 4
            ofs &= 0xF
    return bytes(out)


def run_to(linear, what, tries=1200):
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": linear, "type": "CPU_EXECUTION_ADDRESS",
                           "condition": None})
    mcp("resume_emulator")
    for _ in range(tries):
        st = mcp("read_cpu_state")
        if st["CS"] * 16 + st["IP"] == linear:
            return st
        time.sleep(0.05)
    sys.exit(f"never reached {what} at {linear:#x}")


def relocated(path, load):
    d = open(path, "rb").read()
    nreloc = struct.unpack_from("<H", d, 6)[0]
    hdrpar = struct.unpack_from("<H", d, 8)[0]
    img = bytearray(d[hdrpar * 16:])
    for i in range(nreloc):
        ofs, page = struct.unpack_from("<HH", d, 0x1C + i * 4)
        p = page * 16 + ofs
        struct.pack_into("<H", img, p,
                         (struct.unpack_from("<H", img, p)[0] + load) & 0xFFFF)
    return bytes(img)


def main():
    for f in (PACKED, UNPACKED, DLL):
        if not os.path.exists(f):
            sys.exit(f"missing {f} (run tools/unpack.py first?)")
    proc = subprocess.Popen(
        ["dotnet", DLL, "--Exe", PACKED, "--CDrive", GAME,
         "--McpHttpPort", str(PORT), "--HttpApiPort", "0", "--GdbPort", "0",
         "--RenderingMode", "Sync", "--AudioEngine", "Dummy",
         "--HeadlessMode", "Minimal", "--WarningLogs", "--ReloadCfgGraph", "false",
         "--Debug"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        for _ in range(900):
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health",
                                          timeout=2).status == 200:
                    break
            except Exception:
                time.sleep(0.1)
        else:
            sys.exit("MCP never came up")

        load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
        print(f"load={load:04x}")

        st = run_to(load * 16 + COPY + RELOCATE, "the end of decompression")
        produced = st["ES"] * 16 + st["EDI"] - load * 16
        mine = relocated(UNPACKED, load)
        print(f"decompressor produced {produced} bytes; unpack.py produced {len(mine)}")
        if produced != len(mine):
            print(f"LENGTH MISMATCH -- off by {len(mine) - produced}")
            return 1

        entry = load * 16 + ENTRY_IP
        st = run_to(entry, "the real entry")
        print(f"stopped at {st['CS']:04x}:{st['IP']:04x} after {st['Cycles']} cycles")

        theirs = read_block(load, 0, len(mine))
        bad = [i for i in range(len(mine)) if mine[i] != theirs[i]]
        print(f"compared {len(mine)} bytes ({len(mine)/1024:.0f} KB)")
        if not bad:
            print("IDENTICAL -- unpack.py reproduces what the stub decompresses")
            return 0
        print(f"{len(bad)} bytes differ, first at {bad[0]:#x}")
        for i in bad[:8]:
            print(f"   {i:#08x}  ours {mine[i]:02x}  emulator {theirs[i]:02x}")
        return 1
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except OSError:
            pass


sys.exit(main())

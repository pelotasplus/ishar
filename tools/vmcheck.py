#!/usr/bin/env python3
"""
T38: does the main.io disassembly agree with what the VM actually executes?

`tools/vmdis.py --stats` reporting "97% decoded as instructions" proves nothing:
219 of 231 byte values are valid opcodes, so a linear walk decodes to ~97% from any
offset, aligned or not (T37). The number is the same for a listing that is wrong end
to end.

This is the check that can fail. `vm_run` (seg_0000:26eb) is `sub ah,ah / lodsb`, so
at its entry SI is the address of the next opcode -- a real instruction boundary by
definition. Sample it live and ask how many of those addresses vmdis also calls a
boundary. A misaligned listing fails immediately: its boundaries fall between the
real ones.

    tools/vmcheck.py [seconds] [--samples N]
"""
import json, os, re, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
from rsp import Rsp
_ns = {}
exec(open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0], _ns)
decode = _ns["decode"]
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))


def mcp(t, a=None):
    b = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": t, "arguments": a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=60).read().decode().splitlines():
        if ln.startswith("data:"):
            j = json.loads(ln[5:]); return j.get("result", {}).get("structuredContent", j)


def boundaries():
    """Instruction start offsets, from vmdis's own listing."""
    # vmdis truncates at --lines (default 400); the whole file is wanted here.
    out = subprocess.run([os.path.join(HERE, "tools", "vmdis.py"), "main.io",
                          "--lines", "1000000"], capture_output=True, text=True).stdout
    b = set()
    for ln in out.splitlines():
        m = re.match(r"\s*(\d+)\s+[0-9a-f]{2}\s", ln)
        if m:
            b.add(int(m.group(1)))
    return b


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    secs = int(args[0]) if args else 30
    want = int(sys.argv[sys.argv.index("--samples") + 1]) if "--samples" in sys.argv else 4000

    if "--stepper" in sys.argv:
        # T39: boundaries from the stepper (tools/vmi.py) rather than vmdis's table.
        import importlib.util
        sp = importlib.util.spec_from_file_location("vmi", os.path.join(HERE, "tools", "vmi.py"))
        vmi = importlib.util.module_from_spec(sp); sp.loader.exec_module(vmi)
        d = vmi.decode(open(os.path.join(GAME, "main.io"), "rb").read())[0]
        bset, pc, seen = set(), 0, 0
        while pc is not None and pc < len(d) and seen < 200000:
            seen += 1
            bset.add(pc)
            pc = vmi.step(d, pc)
        print(f"stepper: {len(bset)} boundaries, walked to {max(bset)} of {len(d)}")
    else:
        bset = boundaries()
    script = decode(open(os.path.join(GAME, "main.io"), "rb").read())[0]
    if "--stepper" not in sys.argv: print(f"vmdis: {len(bset)} instruction boundaries over {len(script)} bytes of main.io")

    load = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
    entry = load * 16 + 0x26eb                      # vm_run, before its lodsb
    g = Rsp(st["gdb"])
    mcp("clear_breakpoints")
    mcp("add_breakpoint", {"address": entry, "type": "CPU_EXECUTION_ADDRESS", "condition": None})
    print(f"break at {entry:#x} = vm_run (seg_0000:26eb); sampling DS:SI for {secs}s")

    g.cont()          # a previous probe killed mid-run leaves the machine paused
    samples, t0 = [], time.time()
    while time.time() - t0 < secs and len(samples) < want:
        g.cont()
        if g.wait_stop(timeout=max(1, secs - (time.time() - t0))) is None:
            continue
        r = g.registers()
        if r["ip"] != entry:                        # unmasked; ip is linear (CLAUDE.md)
            continue
        samples.append((r["ds"], r["si"] & 0xffff))
    mcp("clear_breakpoints"); g.cont()

    if not samples:
        sys.exit("no samples -- is the VM running?")

    # Resolve the script base by matching bytes, not by assuming it (T27's method).
    # Anchor on a run that is unique WITHIN main.io and absent from every other
    # asset. A 24-byte run matched on "first asset alphabetically" attributed live
    # samples to frise.io and then gerdep.io on consecutive runs; a cross-asset
    # check at 64 bytes showed both were wrong and the script was main.io all along.
    others = []
    for n in sorted(os.listdir(GAME)):
        if n.lower().endswith(".io") and n.lower() != "main.io":
            try: others.append(decode(open(os.path.join(GAME, n), "rb").read())[0])
            except Exception: pass
    base = None
    for ds, si in samples:
        run = bytes(g.read_mem(ds * 16 + si, 64))
        i = script.find(run)
        if i < 0 or script.find(run, i + 1) >= 0:
            continue
        if any(d.find(run) >= 0 for d in others):
            continue
        base = ds * 16 + si - i
        break
    if base is None:
        # Not a failure of the check: it means every sample was running a script that
        # is not main.io. Say which asset, because that is T37's whole question.
        print("no sample was inside main.io; identifying the scripts that ran instead:")
        assets = {}
        for n in sorted(os.listdir(GAME)):
            if n.lower().endswith(".io"):
                try:
                    assets[n] = decode(open(os.path.join(GAME, n), "rb").read())[0]
                except Exception:
                    pass
        found = {}
        for ds, si in samples[:60]:
            run = bytes(g.read_mem(ds * 16 + si, 24))
            for n, d in assets.items():
                if d.find(run) >= 0:
                    found[n] = found.get(n, 0) + 1
                    break
        for n, c in sorted(found.items(), key=lambda kv: -kv[1]):
            print(f"   {n}: {c} samples")
        if not found:
            print("   none of the 98 assets contains those bytes")
        sys.exit(0)
    print(f"script base = {base:#x}  (main.io offset = DS*16+SI - base)")

    inside = [(d, s) for d, s in samples if 0 <= d * 16 + s - base < len(script)]
    hit = [1 for d, s in inside if (d * 16 + s - base) in bset]
    outside = len(samples) - len(inside)
    pct = 100.0 * len(hit) / len(inside) if inside else 0.0
    print(f"\nsamples {len(samples)}   in main.io {len(inside)}   elsewhere {outside}")
    print(f"on an instruction boundary: {len(hit)}/{len(inside)} = {pct:.3f}%")
    bad = [d * 16 + s - base for d, s in inside if (d * 16 + s - base) not in bset]
    if bad:
        u = sorted(set(bad))
        print(f"{len(u)} distinct offsets vmdis does not call a boundary:")
        for o in u[:15]:
            print(f"   {o}")
    json.dump({"samples": len(samples), "inside": len(inside), "pct": pct,
               "bad": sorted(set(bad))[:200]},
              open(os.path.join(HERE, ".ish", "vmcheck.json"), "w"), indent=1)


main()

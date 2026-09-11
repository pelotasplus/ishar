#!/usr/bin/env python3
"""
T37f: entry points by polling DS:SI, not by breaking on vm_run.

A breakpoint drowns in ~340 background stops/second (measured with one armed on an
address that never executes), each costing a register read, which stalls the game so
the thing being measured never happens. Polling does not stop the machine.

`offset = SI` and `base = DS*16` are exact (FORMATS 7.6), so a sample needs no
anchoring. Attribution uses the strict test -- a 64-byte run unique within its asset and
absent from all 97 others -- and is only paid for when DS is a segment not seen before,
which is what makes the poll affordable.

    tools/t37f-poll.py <seconds>
"""
import json, os, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ns = {}
exec(open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0], _ns)
decode = _ns["decode"]
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})

assets = {}
for n in sorted(os.listdir(GAME)):
    if n.lower().endswith(".io"):
        try: assets[n] = decode(open(os.path.join(GAME, n), "rb").read())[0]
        except Exception: pass
print(f"{len(assets)} assets loaded")

def attribute(ds, si):
    d = mcp("read_memory", {"segment": ds, "offset": si, "length": 64})
    raw = bytes.fromhex(d.get("Data", ""))
    if len(raw) < 64:
        return None
    cands = [(n, a.find(raw)) for n, a in assets.items()
             if a.find(raw) >= 0 and a.find(raw, a.find(raw) + 1) < 0]
    return cands[0] if len(cands) == 1 else None

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 120
LOAD = mcp("read_dos_program_state")["CurrentProgramSegmentPrefix"] + 0x10
first, allpc, tried, samples, invm, t0 = {}, {}, set(), 0, 0, time.time()
while time.time() - t0 < secs:
    cpu = mcp("read_cpu_state")
    ds, si = cpu["DS"], cpu["ESI"] & 0xffff
    samples += 1
    # SI is only the script program counter while the CPU is inside vm_run's fetch loop
    # (seg_0000:26eb..26f8). Without this the poll attributes any moment SI happens to
    # point into an asset buffer -- string moves, block copies -- which is not an entry
    # point at all. CS must be the load segment too.
    if cpu["CS"] != LOAD or not (0x26eb <= cpu["IP"] <= 0x26f8):
        continue
    invm += 1
    key = (ds, si // 16)              # retry a segment as SI moves into new regions
    if key in tried:
        continue
    tried.add(key)
    hit = attribute(ds, si)
    if hit:
        allpc.setdefault(hit[0], set()).add(hit[1])
        if hit[0] not in first:
            first[hit[0]] = (hit[1], round(time.time() - t0, 1))
            print(f"  {time.time()-t0:6.1f}s  DS={ds:04x} SI={si:04x}  -> {hit[0]} offset {hit[1]}")
print(f"\n{samples} samples in {secs:.0f}s ({samples/secs:.0f}/s); {invm} inside vm_run; {len(tried)} attributions tried")
print("first offset seen per asset:", json.dumps({k: v[0] for k, v in first.items()}, indent=1))
json.dump({"first": {k: v[0] for k, v in first.items()},
           "all": {k: sorted(v) for k, v in allpc.items()}},
          open(os.path.join(HERE, ".ish", "t37f.json"), "w"), indent=1)

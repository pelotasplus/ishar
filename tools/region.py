#!/usr/bin/env python3
"""Read the party's region id, the authoritative one.

`gerdep.io` picks the panel caption with statement 0x2f -- a switch: an expression, a case
count, a bias word, then one displacement word per case. Its expression is
`1e ac 3e` = vm_op_load_byte_global 0x3eac, so the region id is the byte at
es:[ss:[0bf6] + 0x3eac]. Reading it beats scraping the caption, which shares its buffer
with filenames and message text (FINDINGS 4.19b).
"""
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = json.load(open(os.path.join(HERE, ".ish", "state.json")))
def mcp(t, a=None):
    b = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                    "params":{"name":t,"arguments":a or {}}}).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{st['port']}/mcp", data=b, method="POST",
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    for ln in urllib.request.urlopen(r, timeout=30).read().decode().splitlines():
        if ln.startswith("data:"):
            return json.loads(ln[5:])["result"].get("structuredContent", {})
NAMES = ["FRAGONIR", "ANGARAHN", "OSGHIROD", "LOTHARIA", "RHUDGAST", "FIMNUIRH",
         "ARAGARTH", "KANDOMIR", "SILMATIL", "URSHURAK", "BALDARON", "VARGAEON",
         "ZENDORIA", "GIL-ARAS", "HALINDOR", "ULDONYAR", "VALATHAR", "ELWINGIL",
         "FHULGROD", "ISHAR", "L'OCEAN"]
GLOBAL = 0x3EAC

def read():
    ss = mcp("read_cpu_state")["SS"]
    p = bytes.fromhex(mcp("read_memory", {"segment": ss, "offset": 0x0bf6, "length": 4})["Data"])
    off, seg = int.from_bytes(p[:2], "little"), int.from_bytes(p[2:], "little")
    rid = bytes.fromhex(mcp("read_memory",
        {"segment": seg, "offset": (off + GLOBAL) & 0xffff, "length": 1})["Data"])[0]
    pos = bytes.fromhex(mcp("read_memory", {"segment": ss, "offset": 0x644c, "length": 2})["Data"])
    return (pos[0], pos[1]), rid

def main():
    if len(sys.argv) > 2:                      # transect: key, count
        key, n = sys.argv[1], int(sys.argv[2])
        for _ in range(n):
            (r, c), rid = read()
            nm = NAMES[rid] if rid < len(NAMES) else f"?{rid}"
            print(f"  ({r:2},{c:2}) region {rid:2} {nm}", flush=True)
            subprocess.run([os.path.join(HERE, "tools", "ish"), "keys", key], capture_output=True)
            time.sleep(0.85)
    else:
        (r, c), rid = read()
        print(f"({r},{c}) region {rid} {NAMES[rid] if rid < len(NAMES) else '?'}")

main()

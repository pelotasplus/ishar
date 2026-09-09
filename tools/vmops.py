#!/usr/bin/env python3
"""
Classify the VM's opcode handlers by what they do (T28).

Every handler is a short run of instructions ending in `ret` or a jump. Reading
135 of them by hand is slow and error-prone; reading them mechanically is not,
because the interesting categories have unmistakable signatures:

  writes SI                 -> control flow (SI is the script program counter)
  calls through a register  -> the bridge from script to native engine
  cmp/test then sets DX     -> comparison
  arithmetic on DX          -> the accumulator ops

Prints one line per opcode, with the opcode number derived from the handler
table: `jmp cs:[di+01f2]` indexes by an unscaled byte, so opcode == table offset.
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDR = 0x250
IMG = open(os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com",
                        "start-unpacked.exe"), "rb").read()
LISTING = os.path.join(HERE, "ishar-listing.txt")

# offset -> (mnemonic, operands) for seg_0000
code = {}
line_re = re.compile(r"^seg_0000:([0-9a-f]{4})\s+([a-z][a-z0-9]*)\s*(.*?)\s*$")
for ln in open(LISTING):
    m = line_re.match(ln)
    if m and m.group(2) not in ("loc", "db", "dw"):
        off = int(m.group(1), 16)
        if off not in code:
            code[off] = (m.group(2), m.group(3))


def body(start, limit=40):
    """Instructions from `start` until the handler returns or jumps away."""
    out, off = [], start
    for _ in range(limit):
        if off not in code:
            break
        mn, ops = code[off]
        out.append((off, mn, ops))
        if mn in ("ret", "retf", "jmp"):
            break
        nxt = [o for o in code if o > off]
        if not nxt:
            break
        off = min(nxt)
    return out


def classify(ins):
    mns = [m for _, m, _ in ins]
    text = " | ".join(f"{m} {o}" for _, m, o in ins)
    tags = []
    # A branch writes the program counter and does not put it back. Handlers that
    # `push si` around a buffer walk (ss:[0c58] is a string workspace) restore it
    # and are not control flow, which is what a looser test got wrong.
    writes_si = re.search(r"\b(add|sub)\s+si,|\bmov\s+si,\s*(ax|dx|bx)\b", text)
    if writes_si and "pop si" not in text:
        tags.append("CONTROL-FLOW")
    # A far call through a stored pointer -- `call [0941:0131]` -- is the bridge
    # out of the interpreter into engine code in another segment.
    if re.search(r"call\s+\[[0-9a-f]{4}:[0-9a-f]{4}\]", text) or \
       re.search(r"call\s+(word ptr )?\[(bx|di|si)", text) or "call cs:" in text:
        tags.append("NATIVE-CALL")
    if "cmp" in mns or "test" in mns:
        tags.append("COMPARE")
    if any(m in mns for m in ("add", "sub", "imul", "mul", "idiv", "div",
                              "and", "or", "xor", "neg", "shl", "shr")):
        tags.append("ARITH")
    if re.search(r"mov\s+es:\[bp", text) or re.search(r"mov\s+\[bx\], ", text):
        tags.append("STORE")
    return tags or ["load/other"]


TABLE = 0x01f2
for a in sys.argv[1:]:
    if a.startswith("--table="):
        TABLE = int(a.split("=")[1], 0)
table = {}
for opc in range(0, 256, 2):
    o = HDR + TABLE + opc
    if o + 2 > len(IMG):
        break
    w = struct.unpack_from("<H", IMG, o)[0]
    if 0x100 <= w <= 0x9410:
        table[opc] = w

args = [a for a in sys.argv[1:] if not a.startswith("--")]
want = args[0] if args else None
counts = {}
for opc, addr in sorted(table.items()):
    ins = body(addr)
    tags = classify(ins)
    for t in tags:
        counts[t] = counts.get(t, 0) + 1
    if want and want not in tags:
        continue
    txt = " ; ".join(f"{m} {o}".strip() for _, m, o in ins[:7])
    print(f"op {opc:#04x} -> seg_0000:{addr:04x}  [{','.join(tags):28s}] {txt[:96]}")
print("\ntotals:", counts)

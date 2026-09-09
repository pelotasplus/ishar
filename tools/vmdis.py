#!/usr/bin/env python3
"""
Disassemble an Ishar script (T30).

`main.io` is the program the game runs (FORMATS.md section 7). vm_run fetches an
opcode byte, indexes the word-scaled table at image 0x24, and calls the handler;
the handler consumes its own operands from the same stream with lodsb/lodsw. So
the operand layout of every instruction is readable from its handler, and that is
where this table comes from -- nothing is guessed.

    tools/vmdis.py main.io              # listing
    tools/vmdis.py main.io --stats      # how much decoded, and which opcodes
    tools/vmdis.py main.io --from 3270  # start elsewhere
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDR = 0x250
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
IMG = open(os.path.join(GAME, "start-unpacked.exe"), "rb").read()
_ns = {}
exec(open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0], _ns)
decode = _ns["decode"]

# ---- the statement table, read from the image -------------------------------
TABLE = {}
for opc in range(231):
    w = struct.unpack_from("<H", IMG, HDR + 0x24 + opc * 2)[0]
    if 0x100 <= w <= 0x9410:
        TABLE[opc] = w

# ---- each handler's instructions, from the listing --------------------------
CODE = {}
NAME = {}
for ln in open(os.path.join(HERE, "ishar-listing.txt")):
    m = re.match(r"^seg_0000:([0-9a-f]{4})\s+([a-z][a-z0-9]*)\s*(.*?)\s*$", ln)
    if m and m.group(2) not in ("loc", "db", "dw"):
        o = int(m.group(1), 16)
        CODE.setdefault(o, (m.group(2), m.group(3)))
    m2 = re.match(r"^seg_0000:([0-9a-f]{4})\s+([A-Za-z_]\w*):\s*$", ln)
    if m2:
        NAME[int(m2.group(1), 16)] = m2.group(2)


HANDLERS = set()          # filled after TABLE is built; every handler start


def operands(addr, limit=40):
    """Operand widths a handler reads, in order: 'b' for lodsb, 'w' for lodsw.

    Stops at the handler's first ret/jmp. A `lodsb` inside a backward jump is a
    string skip rather than a fixed operand, which is why 0x45 is special-cased.
    """
    out, off, seen = [], addr, 0
    while seen < limit:
        seen += 1
        if off not in CODE:
            break
        mn, ops = CODE[off]
        if mn == "lodsb":
            out.append("b")
        elif mn == "lodsw":
            out.append("w")
        if mn in ("ret", "retf", "jmp"):
            break
        nxt = [o for o in CODE if o > off]
        if not nxt:
            break
        off = min(nxt)
        # A handler whose `ret` is not decoded in the listing would otherwise be
        # walked straight out of, into the next routine, whose own lodsb gets
        # counted as an operand -- which made five opcodes exactly one byte too
        # long (T30b). Every handler start is known, so stop on reaching one.
        if off in HANDLERS and off != addr:
            break
    return out


HANDLERS.update(TABLE.values())
OPS = {opc: operands(addr) for opc, addr in TABLE.items()}
# vm_op_load_asset reads `lodsw` for the id and then loops `lodsb` to skip the
# inline name. operands() cannot tell that trailing lodsb from a fixed operand, so
# the layout is stated here: a word, then a NUL-terminated string.
STRING_OPS = {0x45: ["w"]}


def disasm(data, start=0, end=None):
    end = len(data) if end is None else end
    out, pc, decoded, unknown = [], start, 0, 0
    while pc < end:
        opc = data[pc]
        if opc not in TABLE:
            out.append((pc, opc, None, f"db {opc:#04x}", 1))
            pc += 1
            unknown += 1
            continue
        p = pc + 1
        args, txt = [], []
        for kind in (STRING_OPS.get(opc) or OPS.get(opc, [])):
            if kind == "b" and p < end:
                args.append(data[p]); txt.append(f"{data[p]:#04x}"); p += 1
            elif kind == "w" and p + 1 < end:
                v = struct.unpack_from("<H", data, p)[0]
                args.append(v); txt.append(f"{v:#06x}"); p += 2
        if opc in STRING_OPS:
            s = bytearray()
            while p < end and data[p]:
                s.append(data[p]); p += 1
            p += 1
            txt.append('"%s"' % s.decode("latin-1"))
        name = NAME.get(TABLE[opc], f"op_{opc:02x}")
        out.append((pc, opc, args, f"{name} {' '.join(txt)}".strip(), p - pc))
        decoded += p - pc
        pc = p
    return out, decoded, unknown


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = argv[0] if argv else "main.io"
    path = src if os.path.exists(src) else os.path.join(GAME, src)
    data = decode(open(path, "rb").read())[0]
    start = int(sys.argv[sys.argv.index("--from") + 1], 0) if "--from" in sys.argv else 0
    lst, decoded, unknown = disasm(data, start)
    if "--stats" in sys.argv:
        import collections
        c = collections.Counter(o for _, o, a, _, _ in lst if a is not None)
        print(f"{src}: {len(data)} bytes, {decoded} decoded as instructions "
              f"({100*decoded//len(data)}%), {unknown} bytes not an opcode")
        print(f"{len(c)} distinct opcodes used")
        for opc, n in c.most_common(20):
            nm = NAME.get(TABLE[opc], f"op_{opc:02x}")
            print(f"   {opc:#04x} {nm:28s} x{n:<5d} operands {''.join(OPS.get(opc, [])) or '-'}")
        return
    limit = int(sys.argv[sys.argv.index("--lines") + 1]) if "--lines" in sys.argv else 400
    for pc, opc, args, txt, ln in lst[:limit]:
        print(f"{pc:6d}  {opc:02x}  {txt}")


if __name__ == "__main__":
    main()

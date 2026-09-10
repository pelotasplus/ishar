#!/usr/bin/env python3
"""
T39: a length-accurate stepper for Ishar's script bytecode.

Why a stepper and not a table: 79 of 230 statement opcodes call the expression
evaluator inside their handler (FORMATS 7.3), so the bytes after them belong to a
DIFFERENT instruction set -- the byte-scaled table at 0x01f2 -- and the statement's
length depends on how that nested expression parses. No per-opcode width can say how
long such a statement is, which is why tools/vmdis.py drifts.

Everything here is read out of the image and the listing; nothing is hand-entered.

  statement  cs:[0x24 + opc*2]   word-scaled, CALLed, handler ends in `ret`
  load/expr  cs:[0x1f2 + opc]    BYTE-scaled, JMPed to, so opcodes are even
  store      cs:[0x29c + opc]
  add-assign cs:[0x2d8 + opc]

    tools/vmi.py <asset> --from N [--count N]     step and print
    tools/vmi.py --selftest                       widths and table sanity
"""
import os, re, struct, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(HERE, "ishar_legend_of_the_fortress_DOSGamer.com")
IMG = open(os.path.join(GAME, "start-unpacked.exe"), "rb").read()
HDR = 0x250
_ns = {}
exec(open(os.path.join(HERE, "tools", "io.py")).read().split("def main()")[0], _ns)
decode = _ns["decode"]

# ---- the listing, minus its label lines ------------------------------------
# A label line matches the instruction pattern with `vm` as the mnemonic, and it
# comes first, so keeping it discards the real instruction (T38).
CODE, NAME = {}, {}
for ln in open(os.path.join(HERE, "ishar-listing.txt")):
    m2 = re.match(r"^seg_0000:([0-9a-f]{4})\s+([A-Za-z_]\w*):\s*$", ln)
    if m2:
        NAME[int(m2.group(1), 16)] = m2.group(2)
        continue
    m = re.match(r"^seg_0000:([0-9a-f]{4})\s+([a-z][a-z0-9]*)\s*(.*?)\s*$", ln)
    if m and m.group(2) not in ("loc", "db", "dw"):
        CODE.setdefault(int(m.group(1), 16), (m.group(2), m.group(3)))


def table(base, scale, n):
    t = {}
    for opc in range(n):
        w = struct.unpack_from("<H", IMG, HDR + base + opc * scale)[0]
        if 0x100 <= w <= 0x9410:
            t[opc] = w
    return t


STMT = table(0x24, 2, 231)
EXPR = {o: a for o, a in table(0x1f2, 1, 240).items() if o % 2 == 0}
STORE = {o: a for o, a in table(0x29c, 1, 120).items() if o % 2 == 0}
ADDA = {o: a for o, a in table(0x2d8, 1, 168).items() if o % 2 == 0}
STARTS = set(STMT.values()) | set(EXPR.values()) | set(STORE.values()) | set(ADDA.values())
EXPR_ENTRY = {0x69a6, 0x69a9, 0x69ab, 0x69b5, 0x69b8}


def walk(addr, limit=60):
    """(operand widths, calls-an-expression, is-a-branch) for one handler."""
    ops, expr, branch, off, n = [], False, False, addr, 0
    while n < limit:
        n += 1
        if off not in CODE:
            break
        mn, a = CODE[off]
        if mn == "lodsb":
            ops.append("b")
        elif mn == "lodsw":
            ops.append("w")
        elif mn in ("call", "jmp") and re.search(r"069a[689b5]", a):
            expr = True
        elif mn == "add" and a.startswith("si,"):
            branch = True
        if mn in ("ret", "retf"):
            break
        nxt = [o for o in CODE if o > off]
        if not nxt:
            break
        off = min(nxt)
        if off in STARTS and off != addr:
            break
    return ops, expr, branch


INFO = {o: walk(a) for o, a in STMT.items()}
EINFO = {o: walk(a) for o, a in EXPR.items()}


def step_expr(d, pc, depth=0):
    """Length of one expression starting at pc."""
    if depth > 8 or pc >= len(d):
        return pc
    opc = d[pc]
    if opc not in EINFO:
        return pc + 1
    ops, expr, _ = EINFO[opc]
    pc += 1
    if expr:
        pc = step_expr(d, pc, depth + 1)
    for w in ops:
        pc += 1 if w == "b" else 2
    return pc


# Statements whose length depends on their own operands. No table can express these,
# and they are why a table-driven disassembler drifts (FORMATS 7.3).
#
# 0x29, handler seg_0000:5713 -- a block initialiser:
#     lodsw            ; destination offset
#     lodsb            ; cx = count
#     lodsb            ; one byte stored
#     inc cx
#     jmp .test
#   .body: lodsw       ; a WORD per further iteration
#   .test: sub di,2 / loop .body
# `loop` decrements first, so the body runs cx-1 times: total = 5 + 2*(count).
# Worked against the live samples: at 96 the body swallows `5a 00`, giving 103; at 143
# it swallows `1a 00`, giving 150. Both are offsets the running VM reported as
# instruction boundaries and vmdis did not (T38/T38b).
def step_var(d, pc):
    opc = d[pc]
    # 0x46, handler seg_0000:2ded -- declares an entity and copies its record inline:
    #     lodsw / lodsb / mov cx,20h / mov di,bx / add di,6 / rep movsb
    # `rep movsb` takes its source from SI, so 32 bytes of the script stream are the
    # operand. 1 + 2 + 1 + 32 = 36. main.io's first two statements are both this, at
    # offsets 24 and 60, which is exactly the 24 -> 60 -> 96 the live VM steps through.
    if opc == 0x46:
        return pc + 36
    if opc == 0x29:
        if pc + 4 >= len(d):
            return None
        count = d[pc + 3]
        return pc + 5 + 2 * count
    return None


def step(d, pc):
    """Next statement offset, or None when the opcode is unknown."""
    if pc >= len(d):
        return None
    v = step_var(d, pc)
    if v is not None:
        return v
    opc = d[pc]
    if opc not in INFO:
        return None
    ops, expr, _ = INFO[opc]
    pc += 1
    if expr:
        pc = step_expr(d, pc)
    for w in ops:
        pc += 1 if w == "b" else 2
    return pc


def main():
    if "--selftest" in sys.argv:
        print(f"statement {len(STMT)}  expr {len(EXPR)}  store {len(STORE)}  addassign {len(ADDA)}")
        print(f"statements embedding an expression: {sum(1 for v in INFO.values() if v[1])}")
        print(f"expressions embedding an expression: {sum(1 for v in EINFO.values() if v[1])}")
        return
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = args[0] if args else "main.io"
    d = decode(open(os.path.join(GAME, src), "rb").read())[0]
    pc = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 0
    n = int(sys.argv[sys.argv.index("--count") + 1]) if "--count" in sys.argv else 20
    for _ in range(n):
        nxt = step(d, pc)
        nm = NAME.get(STMT.get(d[pc], -1), f"op_{d[pc]:02x}") if pc < len(d) else "?"
        print(f"{pc:6d}  {d[pc]:02x}  {nm:28s} -> {nxt}")
        if nxt is None:
            break
        pc = nxt


if __name__ == "__main__":
    main()

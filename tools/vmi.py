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
import json, os, re, struct, sys

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
    """Read a dispatch table.

    The lower bound is 0x20, not 0x100. Several opcodes are no-ops whose handler is a
    bare `ret` in the four spare bytes just below the tables: image 0x20..0x23 holds
    `05 c3 c3 c3`, and opcode 0x04's entry is literally 0x0022. A 0x100 floor throws
    those away and the walk then stalls on a perfectly valid no-op -- which is what
    stopped stepping main.io at offset 758 (T39b). tools/vmdis.py has the same floor
    and the same hole.
    """
    t = {}
    for opc in range(n):
        w = struct.unpack_from("<H", IMG, HDR + base + opc * scale)[0]
        if 0x20 <= w <= 0x9410:
            t[opc] = w
    return t


STMT = table(0x24, 2, 231)
EXPR = {o: a for o, a in table(0x1f2, 1, 240).items() if o % 2 == 0}
STORE = {o: a for o, a in table(0x29c, 1, 120).items() if o % 2 == 0}
ADDA = {o: a for o, a in table(0x2d8, 1, 168).items() if o % 2 == 0}
STARTS = set(STMT.values()) | set(EXPR.values()) | set(STORE.values()) | set(ADDA.values())
EXPR_ENTRY = {0x69a6, 0x69a9, 0x69ab, 0x69b5, 0x69b8}


def walk(addr, limit=60):
    """Facts about one handler, read from its instructions.

    Returns (operand widths, calls-an-expression, branch-shape or None). The branch
    shape is what recursive traversal needs and every branch handler in this VM is
    built from the same four parts:
        lodsb/lodsw   how wide the displacement is
        inc si        a skipped byte after it, so the base is one further on
        jz/jnz        a test, so the fall-through is live as well as the target
        es:[bp-0ah]   a return address pushed into the frame stack, i.e. a call
    """
    ops, expr, branch, off, n = [], False, False, addr, 0
    skip, cond, call = False, False, False
    while n < limit:
        n += 1
        if off not in CODE:
            break
        mn, a = CODE[off]
        if mn == "lodsb":
            ops.append("b")
        elif mn == "lodsw":
            ops.append("w")
        elif mn == "inc" and a.startswith("si"):
            skip = True
        elif mn in ("jz", "jnz", "je", "jne"):
            cond = True
        elif "bp-0ah" in a:
            call = True
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
    shape = None
    if branch and ops:
        width = 1 if ops[0] == "b" else 2
        base = 1 + width + (1 if skip else 0)
        shape = (base, width, cond, call)
    return ops, expr, shape


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


# ---- control flow --------------------------------------------------------
# Linear walking always ends in a data block eventually: `main.io` has a word table
# at 823 reached only by a jump, and stepping into it stalls on 0xff (T39b). Following
# branches avoids data entirely and needs no evaluation -- take both sides.
#
# Targets read from each handler:
#   0x0a  lodsw / inc si / add si,ax        -> pc+4+i16, unconditional
#   0x08  lodsb / cbw   / add si,ax         -> pc+2+i8,  unconditional
#   0x14  test dx,dx / jnz(add si,3) / ...  -> taken pc+4+i16, else pc+4
#   0x1a  cmp dx,cx  / jnz(add si,3) / ...  -> taken pc+4+i16, else pc+4
#   0x06  lodsw / push si / add si,ax       -> pc+3+i16, and returns to pc+3
def i16(d, o):
    v = d[o] | (d[o + 1] << 8)
    return v - 0x10000 if v & 0x8000 else v


def i8(d, o):
    return d[o] - 256 if d[o] & 0x80 else d[o]


# Statements that END the script rather than continuing. vm_run is a loop -- fetch,
# call the handler, jump back -- so a handler exits it only by discarding vm_run's own
# return address. Exactly two do:
#   0x42  seg_0000:2d94   add sp,2 / ret
#   0x43  seg_0000:2d98   cmp ss:[0c19],0 / jz 2d94 / call 2808 / add sp,2
# They are YIELDS, not stops: the caller saves SI (`mov es:[bp-8],si`) and resumes the
# script there next time, so control does fall through to the following statement and
# traversal must not treat them as terminal.
#
# Treating them as terminal was tried and is wrong: coverage fell 42.8% -> 8.7%. And the
# check that would have supported it fails -- if a yield saved SI just past the opcode,
# every observed first-yield offset would sit one byte after a 0x42/0x43, and none of
# the four does (main.io 256 follows 0x29, logo.io 256 follows 0x14, blancpc.io 801
# follows 0x12, fbuis.io 3960 follows 0x00). So either those offsets are not yields of
# this kind, or the asset/offset attribution behind them is wrong. Unresolved; recorded
# so the idea is not retried blind.
TERMINATORS = set()


def successors(d, pc):
    """Where control can go from the statement at pc, or None if unknown."""
    if pc + 1 >= len(d):
        return None
    opc = d[pc]
    if opc in TERMINATORS:
        return []
    info = INFO.get(opc)
    if info and info[2] and step_var(d, pc) is None:
        base, width, cond, call = info[2]
        if pc + 1 + width > len(d):
            return None
        disp = i8(d, pc + 1) if width == 1 else i16(d, pc + 1)
        after = pc + base
        out = [after + disp]
        if cond or call:            # a test keeps the fall-through; a call returns to it
            out.append(after)
        return out
    nxt = step(d, pc)
    return None if nxt is None else [nxt]


def plausible(d, pc):
    """Could a statement start here? There are exactly 231 opcodes."""
    return 0 <= pc < len(d) and d[pc] in STMT


def traverse_all(d, entries):
    """Traverse from several entry points and merge.

    A script has more than one: `main.io` is entered at 24 by the loader and at 19919
    by the engine, and the second region has no static in-edge from anywhere in the file
    -- five of its statements have zero candidate in-edges and the rest are reachable
    only from those (T39d). Traversing from 24 alone reaches 73.5% of the statements the
    VM actually executes; adding 19919 reaches 100%.
    """
    seen, cov, unk, rej = set(), 0, set(), []
    for e in entries:
        s, c, u = traverse(d, e)
        seen |= s
        unk |= u
        rej += traverse.rejected
    for pc in seen:
        n = step(d, pc)
        cov += (n - pc) if (n and n > pc) else 1
    traverse_all.rejected = rej
    return seen, cov, unk


MAIN_ENTRIES = (24, 19919)      # loader entry, engine handler entry


def traverse(d, entry):
    """Recursive-descent: every statement reachable from entry, and bytes covered.

    Targets are checked before they are followed. A computed target landing on a byte
    with no entry in the 231-opcode table cannot be code, and following one puts the
    walk inside a data block where every later step is garbage -- which is where all 56
    of the earlier stalls came from, each traced back to a different branch rather than
    to one wrong shape. Rejected targets are counted, not silently dropped: they are the
    branches worth looking at.
    """
    seen, todo, unknown, rejected = set(), [entry], set(), []
    while todo:
        pc = todo.pop()
        if pc in seen or pc < 0 or pc >= len(d):
            continue
        seen.add(pc)
        succ = successors(d, pc)
        if succ is None:
            unknown.add(pc)
            continue
        for t in succ:
            if plausible(d, t):
                todo.append(t)
            else:
                rejected.append((pc, t))
    traverse.rejected = rejected
    covered = 0
    for pc in seen:
        n = step(d, pc)
        covered += (n - pc) if (n and n > pc) else 1
    return seen, covered, unknown


def listing(d, entries):
    """A disassembly of the reachable script, in offset order.

    Only statements the traversal actually reaches are printed; everything else is
    marked as data rather than decoded, because a linear walk decodes data just as
    happily as code (FORMATS 7.3).
    """
    seen, _, _ = traverse_all(d, entries)
    out, prev = [], 0
    for pc in sorted(seen):
        if pc > prev:
            out.append(f"{prev:6d}  ---- {pc - prev} bytes not reached ----")
        opc = d[pc]
        nxt = step(d, pc)
        nm = NAME.get(STMT.get(opc, -1), f"op_{opc:02x}")
        raw = " ".join(f"{b:02x}" for b in d[pc:nxt if nxt else pc + 1][:8])
        succ = successors(d, pc)
        flow = ""
        if succ and INFO.get(opc) and INFO[opc][2]:
            flow = "  -> " + ", ".join(str(t) for t in succ)
        out.append(f"{pc:6d}  {raw:24s} {nm:30s}{flow}")
        prev = nxt if nxt else pc + 1
    if prev < len(d):
        out.append(f"{prev:6d}  ---- {len(d) - prev} bytes not reached ----")
    return out


def main():
    if "--listing" in sys.argv:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        src = args[0] if args else "main.io"
        d = decode(open(os.path.join(GAME, src), "rb").read())[0]
        # Entry sets discovered by tools/t37f-poll.py (T37f), so --listing works on any
        # asset that has been observed executing, not just main.io.
        ent = MAIN_ENTRIES
        if src != "main.io":
            try:
                found = json.load(open(os.path.join(HERE, ".ish", "t37f-entries.json")))
                ent = tuple(found[src]["entries"])
            except Exception:
                ent = (24,)
        for ln in listing(d, ent):
            print(ln)
        return
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

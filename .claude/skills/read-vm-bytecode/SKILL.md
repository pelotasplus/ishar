---
name: read-vm-bytecode
description: Use when reading Ishar's script bytecode - decoding a statement, identifying an opcode, or working out what a script does with a value. Carries the four dispatch tables, the encodings that defeat a table-driven disassembler, and what to do when the stepper drifts.
---

# Reading the script VM

The game's logic is bytecode in the `.io` assets, run by a VM whose four dispatch tables
live in `start-unpacked.exe` — **not in the assets**, which is why a file parser alone can
never recover opcode meanings.

| table | at | scaling |
|---|---|---|
| statement | `cs:[0x24 + opc*2]` | word, CALLed, handler ends in `ret` |
| expression | `cs:[0x01f2 + opc]` | **byte**, JMPed to, so opcodes are even |
| store | `cs:[0x029c + opc]` | byte |
| add-assign | `cs:[0x02d8 + opc]` | byte |

`tools/vmi.py` reads all four out of the image. Look an opcode up rather than guessing:

    python3 -c "import sys;sys.path.insert(0,'tools');import vmi;print(hex(vmi.EXPR[0x26]))"
    tools/vmi.py ASSET --listing            render a script
    tools/vmi.py --selftest                 widths and table sanity

## When the listing drifts, read the bytes

`--listing` traverses, and traversal drifts: around a variable-length statement it will
render one clean 10-byte statement as three overlapping decodes with impossible jump
targets. **A target outside the file is the tell.**

The recovery that works: dump the raw decoded bytes, find the opcode in the tables, read
the handler in `ishar-listing.txt`, and step it by hand. That is what cracked the map
access when the traversal around it was nonsense.

    d = decode(open(asset,'rb').read())[0]; print(d[1150:1216].hex())

## Encodings no per-opcode width can express

- **`0x29` is `5 + 2*count`**, with `count` read from its own third operand. Three tasks
  went on two disputed offsets that turned out to be *data inside the preceding
  instruction*. A table-driven disassembler is wrong in kind here; `vmi.py` is a stepper.
- **79 of 230 statements call the expression evaluator**, so the bytes after them belong to
  a different instruction set and the statement's length depends on how that parses.
- **`0x2f` is a jump-table switch**: `2f <expr> <count:u8> [pad to even] <bias:i16>
  <count+1 x i16>`, each displacement relative to its own slot (FORMATS 7.2g).
- **Arrays.** Expression `0x26` is an indexed global byte load, `26 <base:u16>`. The array's
  descriptor sits *below* its data: dimension count at `base-1`, stride words below
  `base-2`. Subscripts come off an expression stack — `0x40` push, `0x36` pop, `0x38` begin
  a sequence, `0x3a`/`0xe4` end it (FORMATS 7.2h).
- **`0x38`'s handler looks like an infinite loop and is not.** `call 069ab / jmp 7150`; the
  terminator does `add sp,2 / ret`, discarding the return address.

## Entry points

A script has a **set** of them, not one. `main.io` is entered at 24 by the loader and at
19919 by the engine; traversing from 24 alone reaches 73.5% of what actually executes.
`.ish/t37f-entries.json` holds the sets, obtained by polling (see `find-consumer`).

**Do not try to find entries statically.** Traversing from every plausible offset and
keeping the regions that close cleanly was tried and scores the real entries 58th to
1903rd out of ~2,000 — real regions contain statements the stepper cannot size and targets
it rejects, so "clean" and "large" are both the wrong signal.

## What this is for

A rewrite cannot extract a table of behaviour, because the behaviour *is* the bytecode —
the world map is read by scene scripts via `26 80 00`, not by any native routine. Reading a
script means either porting it or reimplementing what it does.

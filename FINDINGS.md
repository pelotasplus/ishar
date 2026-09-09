# Ishar 1 — findings

What the game *does*: mechanics, world, content. Byte layouts and file formats live in
`FORMATS.md`; how we plan to get there is in the Vault
(`Projects/Ishar/reverse-engineering-plan/`).

This file is the handover document for the Compose Multiplatform rewrite. Everything
here should be specific enough to implement from, and every claim should say how it was
established. A finding with no evidence line is a guess that will be believed later.

**Conventions**

- Addresses are `segment:offset` as seen at runtime, with the image offset in brackets
  where known: `017D:04BE [+0x04BE]`.
- Every subsection ends with **Evidence:** — how we know. "Read the code at X",
  "watched the write at X", "changed it and the screen did Y".
- Screenshots go in `captures/`, named `<area>-<what>.png`, and are linked from the
  section they illustrate.
- Unknowns are written down as unknowns, in their own **Open** lines. An empty section
  is more useful than a plausible one.

---

## 1. Game logic

### 1.1 Party and characters

Not yet investigated. The party is 5 slots, each with a portrait, ACTION/ATTACK
buttons and a LIFE bar. Starting character in a fresh game is `ARAMIR`.

![party panel](captures/game-party-panel.png)

**Evidence:** screenshot only. See also `captures/game-lake-shore.png`.

**Open:** character record layout, stat list, XP curve, level-up rules, class system.

### 1.2 Combat

Not yet investigated.

**Open:** to-hit and damage formulas, weapon/armour contribution, initiative, what
ACTION vs ATTACK actually dispatch to.

### 1.3 Magic

Not yet investigated.

**Open:** spell list, mana cost table, school/class restrictions, effect dispatch.

### 1.4 Movement and world

The outdoor view is a first-person scene with a compass rose and a DISK icon in the
right-hand panel. Movement responds to the arrow keys; the party walks between
distinct outdoor areas (starting field → lake shore in ~450 steps of driving).

**Evidence:** driven with `key.sh`/MCP, screenshots before and after.

**Open:** map representation, area transitions, coordinate system, collision.

---

## 2. Input

### 2.1 The keyboard is the launcher's, not DOS's

`start.exe` hooks INT 9 at `017D:1072`, reads port 0x60 directly, and translates
scancodes through its own table at `017D:04BE`. Table entry *N* corresponds to
scancode *N+1*. It records a key-down flag per scancode at `017D:031A` and the
translated character of the last key at `017D:0318`, then chains to the previous
handler.

The **letter rows are QWERTY but the number row is French**:

```
sc 02..0B  ->  26 82 22 27 28 60 8A 21 87 85   =  & é " ' ( ` è ! ç à
sc 4F..52  ->  31 32 33 30                     =  keypad 1 2 3 0
sc 10..19  ->  71 77 65 72 74 79 75 69 6F 70   =  q w e r t y u i o p
```

That is why the language menu ("1 - ENGLISH") only answered to the numeric keypad:
pressing top-row `1` delivers `&`. There is no shifted table, so the top row can never
produce a digit. `remap-digits.sh` rewrites those ten entries to `31..30` at runtime.

`start.stp` (14 bytes, `RBVVSAP1J0M1KQ`) carries the launcher's settings, and `KQ`
looks like keyboard=QWERTY — so the QWERTY letter rows are probably that setting
applied to a French base table, with the number row left unconverted. That reading is
unconfirmed.

**Evidence:** disassembled the handler under Spice86; dumped the table; patched the ten
bytes and top-row `1` selected English where it previously did nothing.

![language menu](captures/menu-language.png)

### 2.2 Mouse

The game uses the mouse for its UI. Spice86's `send_mouse_move` did **not** move the
in-game cursor in testing, so mouse-driven paths cannot currently be automated.

**Open:** how the game reads the mouse (INT 33h vs raw PS/2), and what it takes to
drive it.

---

## 3. Boot and screens

### 3.0 What the game reads at startup

In order, from a paused start (`tools/gdbtrace.py`, 7.7 s of wall clock):

| # | call | detail |
|---|---|---|
| 0-2 | `START.STP` | opened, 14 bytes read to `1554:0386`, closed — the settings string |
| 3-4 | `cd.tst` | created and closed — a writability probe of the drive |
| 5-7 | `blancpc.io` | 2500 bytes read whole to `1123:0000` |
| 8-13 | `MAIN.IO` | 6-byte header, 16-byte block, then 8000-byte chunks to `e000:0000` |
| 14-16 | `findfirst` | `main.io`, `mcave.io`, `main.io` — existence checks |
| 17 | `logo.IO` | opened; the Silmarils logo follows |

The buffer at `1554:0386` after the `START.STP` read holds the settings string followed
by setup-screen text (`VIDEO`, `CGA`, `EGA`, "to select options, ENTER to validate"), so
the launcher carries a setup UI we have not seen on screen.

Each call's caller was read off the interrupt frame (`SS:SP` holds the return
address), which locates the code rather than just the behaviour:

| call | returns to | listing address |
|---|---|---|
| open `START.STP` | `1554:0e9f` | `seg_13d7:0e9f` |
| read settings | `1554:0eb4` | `seg_13d7:0eb4` |
| create `cd.tst` | `017d:21a9` | `seg_0000:21a9` |
| open an asset | `017d:1feb` | `seg_0000:1feb` |
| read an asset | `017d:2136` | `seg_0000:2136` |
| close | `017d:20be` | `seg_0000:20be` |

The same open/read/close addresses serve `blancpc.io`, `MAIN.IO` and `logo.IO`, so
assets come through one path — and the container decoder sits just upstream of
`seg_0000:2136`, which is where T10 should start. All are annotated in `ishar.chani`.

After `logo.IO` closes the program makes **no further file calls for at least 130 s**
while the logo is on screen: the language menu that follows needs a keypress, not more
loading. Whether the menu transition itself reads anything is not yet established —
tracing through it needs input, and sending keys over MCP pauses the emulator often
enough to slow the trace badly.

**Evidence:** live INT 21h trace over the GDB stub with an MCP-armed conditional
breakpoint; buffer contents and interrupt frames read back at each stop; four runs, the
first eight calls identical in all four and the full 18-call sequence identical in the
two that ran undisturbed.



Sequence from launch, driven by keyboard:

1. Language menu (`1`-`4`).
2. Authors/credits screen.
3. Intro sequence — Krogh artwork, then the ISHAR title over the fortress. Escape
   skips forward; the whole intro loops back to the language menu if left alone.
4. Gameplay.

Startup to the language menu is roughly 30-40 s of emulated time under Spice86 with
the default instruction time scale.

![Krogh, intro](captures/intro-krogh.png)
![title screen](captures/intro-title.png)

**Evidence:** driven over MCP, screenshot at each step.

---

## 4. Runtime layout

One DOS process, not two. PSP stays `016D` from the launcher through to gameplay while
`CS` moves from `017D` to `0ABE`, so no second program is EXEC'd — the game code is
part of the same image, `0x9410` bytes in. See `FORMATS.md` for the executable itself.

- `017D:` launcher / front-end. Resident for the session. Owns INT 9.
- `0ABE:` main game. Owns INT 8.
- `DS` in-game observed at `99FE` — a large data/heap area well above the code.

**Evidence:** `read_dos_program_state` at two points in the run; CPU state in-game.

**Open:** segment values are stable across runs so far but nothing yet proves they must
be. Do not hard-code them in tooling without checking — `tools/addr.py` reads `load`
from the running emulator rather than assuming it.

### 4.1 Segment map

Derived from the rebuilt relocation table (`tools/segmap.py`): a relocation site whose
patched word sits directly after a `9A` byte is the segment half of a far call, so that
paragraph holds code.

| listing segment | image range | runtime CS at load 017d |
|---|---|---|
| `seg_0000` | `0x00000..0x09410` | `017d` — the launcher |
| `seg_0941` | `0x09410..0x0e970` | `0abe` — the main game |
| `seg_0e97` | `0x0e970..0x13d70` | `1014` |
| `seg_13d7` | `0x13d70..0x15a26` | `1554` |

Four more paragraphs are relocated as far *data* pointers and never called into:
`0bac 0c0b 0fa6 12ab`.

`seg_0941` at image `+0x9410` is exactly the `0abe` seen at runtime, which is the
independent confirmation that the unpacked image and the live process agree.

**Evidence:** `tools/segmap.py` over `start-unpacked.exe`; cross-checked against the
runtime `CS` values observed in Spice86, and against Spice86's own physical address for
the crash (`0abe:3f3a` = `0xeb1a`, which `tools/addr.py` reproduces).

### 4.2 Listing coverage

8.2% from the relocation table's 41 far-call targets alone; 27.9% after importing the
265 functions Spice86 recorded as executed across a language-menu run and a gameplay
run (`tools/symbols.py`). The rest is reached through near calls and indirect jumps.

**Evidence:** `tools/disasm.sh` before and after the import.

---

## 5. Known defects (ours and the game's)

### 5.0 A second garbage-execution fault

A traced boot died with `Instruction requires a memory operand but encoding selects a
register (modrm mod=3)` — a decode failure, so execution had again left real code. Same
family as §5.1 but a different symptom, and it happened while keys were being sent from
a second process during a GDB trace. Not yet characterised; noted so it is not mistaken
for §5.1 when it recurs.

**Evidence:** `.ish/spice86.log` from the T08 attempt; the tracer's socket was reset
when the emulator exited.

### 5.2 Spice86 does not implement the FPU opcodes this game uses

A run died with `Invalid opcode 0xDA at 1014:0F0A`. `0xDA` is an x87 escape, and
Spice86's instruction parser says so plainly:

```
// FPU escapes (0xD8-0xDF): only D9, DB, DD have partial support
```

So the game uses floating point that the emulator cannot execute. This is very likely
the common cause behind §5.0 as well — "Instruction requires a memory operand but
encoding selects a register (modrm mod=3)" is exactly what partial FPU support produces
when it meets a register-form encoding of an opcode it half-knows.

Whether §5.1's timer-vector crash shares the cause is not established: that one lands in
palette data with a stale vector, which is a different signature.

This is a constraint on the whole project, not a bug in the game: any measurement that
reaches FPU code will stop. The options are to implement the missing escapes in the
local Spice86 checkout, to avoid the paths that use them, or to accept short sessions.

**Evidence:** the fault text with its address, and the comment at
`Spice86.Core/Emulator/CPU/CfgCpu/Parser/InstructionParser.cs:354`.

### 5.1 Timer interrupt goes stale — reproducible crash

IRQ0 vectors to `0ABE:0D98`, which is not an interrupt handler: it is ordinary
mid-function code (`cbw / push es / mov AL,[BX+0x4102] / mov CS:[SI+0x069C],AL /
ret near`). The `ret near` pops the interrupt frame's IP, so execution resumes at a
data address — VGA palette data at `0ABE:3F1F` — and runs until `0F 0E` faults as an
invalid opcode at `0ABE:3F3A`.

Spice86 names it exactly:

```
Current function unknown_0ABE_0D98 return instruction NEAR16 at 0ABE:0DA3
  Expected return at EXTERNAL_INTERRUPT call time was 0ABE:0580
  but return will go to 0ABE:3F1F
```

Repro: boot, `1` at the language menu, Escape, wait ~35 s, Escape+Space. Crash within
about a minute. Four "stack delta 2 bytes" warnings precede it.

Not audio-dependent (happens with `AUDIO=none`), not caused by the CFG-graph reload
(happens with it off), not caused by the digit patch (the patched bytes are in the
launcher's table, a different region).

**Open:** whether the game installs the vector and something later overwrites that
code, or the vector's segment word is written against a stale offset. `watch-int8.sh`
exists to catch the install but has not yet observed one.

Two leads fell out of the segment map, both worth following in T18:

- `seg_0000:0d98` is a far-call target in the *launcher* whose first bytes are a
  full interrupt prologue (`push ax/bx/cx/dx/di/si/ds/es/bp; cld; mov ax,0c0b;
  mov ds,ax`). The offset `0x0d98` in the failing vector is therefore the launcher's
  handler offset, paired at runtime with the *game's* segment.
- `seg_0941:1c31` is a far-call target in the game that begins `mov ax,0bac /
  mov ds,ax` and goes on to `mov ax,3508 / int 21` — DOS get-interrupt-vector for
  INT 8. Whatever manages the timer vector runs through there.

Both are among the seeds chani cannot lay out, so read them with Spice86's
`read_disassembly` for now.

**Evidence:** `tools/segmap.py` far-call targets; bytes read from
`start-unpacked.exe`.

**Evidence:** reproduced independently of the original report, same address both times.

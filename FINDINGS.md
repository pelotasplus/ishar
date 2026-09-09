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

### 1.1b The character sheet, read from the game's own labels

`messagee.io` decodes to the English UI strings, which name every field the game shows
for a character:

```
LEVEL        EXPERIENCE     VITALITY      PHYSICAL      MENTAL
ATTRIBUTES:  STRENGTH  CONSTITUTION  AGILITY  INTELLIGENCE  WISDOM
SKILLS:      LOCKPICKING  ORIENTATION  FIRST AID  1 HAND WEAPONS
             2 HANDS WEAPONS  THROWING  SHOOTING  LANGUAGES
```

So a character carries five headline values, five attributes and eight skills. That is
the shape T19 has to find in memory — and it is a much better anchor than hunting for
an unknown structure, since each of these is displayed and therefore stored.

Party actions, from the same file: `GIVE ITEM`, `GIVE MONEY`, `KILL`, `DISMISS`,
`RECRUIT`, `PICK LOCK`, `ORIENTATION`, `FIRST AID`, `MAP`, `CAST SPELL`.

**Evidence:** `tools/io.py` decode of `messagee.io`, whose decoder is verified
byte-for-byte against the emulator on two other files.

### 1.1c Recruitment is a party vote

`TEAM VOTE :` followed by `: OK`, `: NEUTRAL`, `: AGAINST`, and the outcomes
`MEMBER RECRUITED`, `CHARACTER REJECTED`, `COMPLETE PARTY`, `EXPULSION APPROVED`,
`EXPULSION REJECTED`. So existing members vote on whether a candidate joins or is
expelled, and the vote can fail. A rewrite that models recruitment as a simple "add to
party" would miss a real mechanic.

**Evidence:** decoded `messagee.io`.

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

## 3b. Quests and lore

From the decoded text files. These are the game's own words, quoted only as far as
needed to establish the facts.

**The premise.** Krogh murdered Prince Jarel and took his throne in Ishar, "an evil
temple unleashing hordes of monsters". The speaker of the intro is Akeer, one of Jarel's
companions, who fought the earlier Dark Lord Morgoth. Destroying Krogh grants Ishar's
powers and the kingdom.

**Three quests**, given by Azalghorm, "the Spirit, Silmarilian Gods messenger": the
magician's talisman, the exhausted witch, and gaining possession of all of the rune
tablets.

**Named characters and places** appearing in the strings: Akeer, Zach (another of
Jarel's companions, who gives a flask), Deloria, Azalghorm; the country of Angarahn with
a village and the tavern "The Thirsty Barbarian"; a lacustrine city to the north-east
with the taverns "Frogonir's Inn" and one other.

**Copy protection.** `PROTECTION TEST-MANUAL`, `PLEASE USE YOUR MANUAL AND ENTER`,
`WORD  LINE`, `PAGE :` — the game asks for a word from the printed manual. This is a
gate any automated play will hit, and it is not in the roadmap's boot path yet.

**Evidence:** decoded `textine.io` and `messagee.io`.

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

## 6. The game runs on a bytecode virtual machine (T11p)

Diffing Spice86's per-function call counts across 15 seconds of walking around names 57
routines that run in the viewport, and the three hottest are nested: `seg_0000:69a6`
(8,677 calls) drives `seg_0000:69a9` (1,306,037) which drives `seg_0000:69ab`
(3,791,391). That is not a drawing routine, it is a dispatch loop:

```
seg_0000:69a6   bb 7c 27          mov  bx, 277ch
seg_0000:69a9   8b ca             mov  cx, dx
seg_0000:69ab   2b c0             sub  ax, ax
seg_0000:69ad   ac                lodsb                ; fetch the next opcode
seg_0000:69ae   8b f8             mov  di, ax
seg_0000:69b0   2e ff a5 f2 01    jmp  cs:[di+01f2h]   ; through the handler table
```

`SI` is the script's program counter and `cs:[01f2]` is a jump table of **120 distinct
handlers**, all landing inside `seg_0000`'s code and starting at `0x69c7`. A second
interpreter sits at `seg_0000:2937` dispatching through `cs:[029c]` with 56 handlers.

The small routines around `seg_0000:2880`-`28b4` fit the same picture: each is a
two-or-three instruction "advance SI past this operand" helper (`lodsb/cbw/add si,ax`,
`lodsw/add si,ax`, `add si,3`), which is operand skipping, not graphics.

**Why this matters more than the routine it was found looking for.** T11p set out to
find the viewport's sprite blitter. The answer is that the viewport is *driven by
interpreted script*, so combat, magic, quests and character logic -- T21 to T24, the
tasks that have never been located in the disassembly -- are plausibly bytecode rather
than native code. That would explain why 38% instruction coverage has yielded so few
routines anyone can name: a large part of the game is data this listing never decodes.

**Evidence:** call-count diff across a walk (`tools/t11p-diff.py`, `.ish/t11p-walk.json`);
the dispatch instructions read out of live memory at `seg_0000:69a6`; and the tables
dumped from live memory -- 120 of 128 words at `01f2` and 55 of 128 at `029c` fall
inside the code segment, ascending from the byte after the dispatch itself.

**Not established:** what any opcode does, where the scripts live (in the assets or in
the image), or which of the two interpreters is which. See T26 and T27.

### 6.1 The VM's shape and its first opcodes (T26)

The interpreter is a register machine with an inline operand stream:

| | |
|---|---|
| `SI` | script program counter -- every handler starts by `lodsb`/`lodsw`-ing its operands |
| `DX` | the accumulator; nearly every handler ends `mov dx, ax / ret` |
| `ES:BP` | the variable frame -- locals are `es:[bp + offset]` |
| `ss:[0bf6]` | a second base, so there are two variable areas (frame and globals) |
| `cs:[01f2]` | the handler table, indexed by the opcode **byte**, so opcodes are even |

The opcode set is an addressing-mode matrix rather than a list of unrelated
instructions -- the same operation appears once per operand width and once per access
mode, which is why 120 handlers cover so little conceptual ground:

| handler | opcode | what it does |
|---|---|---|
| `seg_0000:69c7` | 0x00 | `DX = imm8` (sign-extended) |
| `seg_0000:69cc` | 0x02 | `DX = imm16` |
| `seg_0000:69e3` | 0x06 | `DX = (int8) es:[bp+imm16]` |
| `seg_0000:69ed` | 0x08 | `DX = es:[bp+imm16]` (word) |
| `seg_0000:69f4` | 0x0a | far form: pushes ES/DS/BX and reloads DS from ES |
| `seg_0000:6a16` | 0x0e | `DX = (int8) es:[bp + vm_index_byte(imm16)]` -- array read |
| `seg_0000:6a52` | 0x1a | `DX = (int8) es:[bp+imm8]` |
| `seg_0000:6a5e` | 0x1c | `DX = es:[bp+imm8]` (word) |
| `seg_0000:6a8b` | 0x22 | indexed byte read, byte operand |
| `seg_0000:6a9a` | 0x24 | indexed word read, byte operand |
| `seg_0000:6acd` | 0x2a | `DX = (int8) es:[ss:[0bf6] + imm16]` -- the global area |

`vm_index_byte` (`seg_0000:6c2e`) is shared by eight handlers, `vm_index_word`
(`6c5b`) and `vm_index_far` (`6c8a`) by the rest -- these are the array index/scale
helpers, and they were among the hottest routines in the walk trace (242k and 195k
calls in 15s).

**Evidence:** handlers read from `ishar-listing.txt` after seeding all jump-table
targets; the table-to-opcode mapping follows from the dispatch reading
`cs:[di+01f2]` with `di` an unscaled byte.

**Coverage:** seeding every jump table in the image (`tools/vmseed.py`, 8 tables, 256
distinct targets) plus the executed-function import took the listing from **38.1% to
45.3%**, and `seg_0e97` from 786 decoded instructions to 1,602.

### 6.2 How Ishar's VM compares to Eye of the Beholder's INF scripts

Worth writing down because it sets the size of the rewrite. EOB2's level scripts
(`../eob/eye-of-the-beholder-file-formats`, `eob.inf`) are a **command list**: about 30
opcodes numbered downward from `0xff`, each one a game verb --

```
0xff Set wall   0xfb Create monster  0xfa Teleport   0xf8 Message   0xf7 Set flag
0xf4 Heal       0xf3 Damage          0xf2 Jump       0xf1 End       0xf0 Return
0xef Call       0xee Conditions      0xec Change level  0xeb Give experience
0xea New item   0xe6 Encounters      0xe5 Wait      0xe3 Text menu
```

Operands are literal bytes, state is a global flag array, and control flow is
Jump/Call/Return/Conditions. There is no expression evaluator, no local variables and no
stack: it is a data format that happens to be executable.

| | EOB2 INF | Ishar |
|---|---|---|
| opcodes | ~30 game verbs | ~460 handlers across 4 tables |
| operands | literal bytes | evaluated expressions |
| variables | global flags only | locals (`ES:BP` frame) **and** globals (`ss:[0bf6]`) |
| arrays | none | yes (`vm_index_byte` / `_word` / `_far`) |
| types | none | byte and word, sign- and zero-extended |
| eval stack | none | yes, `BX` reset to `0x277c` per statement |
| branches | absolute | **PC-relative**, so scripts are position-independent |
| concurrency | none | **cooperative multitasking**, task stack at `ss:[0c56]` |

Three of Ishar's four tables are the same addressing-mode matrix repeated for load, store
and `+=`. Nobody hand-writes that: it is **a compiler's output**. Silmarils had an
in-house language; Westwood had a level editor emitting commands.

**What it costs the rewrite.** For EOB, reading the INF gives you the game logic and a
30-verb interpreter is trivial. For Ishar there is a whole language in the way: either
implement the VM (expressions, frames, arrays, coroutines) or decompile the bytecode back
to source. The verbs actually wanted -- combat, magic, quests -- are not opcodes at all
but **engine primitives called from compiled script**, which is the reason T21-T24 have
never been locatable in the disassembly.

The compensating advantage is regularity: the encoding is uniform enough that a
decompiler is tractable once the primitives are named (T29).

**Evidence:** EOB opcode list from the file-format wiki in `../eob`; Ishar's structure
from FORMATS.md section 6, which was measured from the image and live memory.

### 6.3 The engine's script-visible API (T29)

`vm_statement_table` (image `0x24`, 231 entries, word-scaled) holds every statement and
every engine primitive. **155 handlers are now named in `ishar.chani` with a signature** --
arity (how many expression arguments the handler evaluates), the inline operand bytes it
fetches itself, and the engine variables it writes. A primitive's signature is readable
directly from its handler because arguments arrive one evaluator call at a time:

```
vm_stmt_ba (seg_0000:296b)   arity 5, sinks ss:[0ba8]:w ss:[0ba0]:w ss:[0ba2]:b
                                            ss:[0ba4]:b ss:[0ba6]:w
vm_stmt_bf (seg_0000:2994)   arity 3, sinks ss:[0c02]:w ss:[0c04]:w ss:[0c06]:w
                                            ss:[0c0e]:b
```

Seeding them took the listing from 45.3% to **49.6%**, and `seg_0000` from 6,512
undecoded bytes to 2,732 -- so the statement handlers were most of what was still dark in
that segment.

**Which opcodes run while the party moves.** Cross-referencing the call-count diff taken
across 15s of walking (section 6) against the table identifies nine:

| opcode | handler | calls while walking |
|---|---|---|
| 0x1f | `seg_0000:2937` | 785,731 |
| 0x14 | `seg_0000:289c` | 482,187 |
| 0x20 | `vm_stmt_assign` | 215,743 |
| 0x15 | `seg_0000:28a9` | 156,565 |
| 0x12 | `vm_skip_operand_b` | 83,543 |
| 0x16 | `seg_0000:28b4` | 50,802 |
| 0x1e | `seg_0000:2915` | 39,493 |
| 0x42 | `seg_0000:2d94` | 23,379 |
| 0x13 | `vm_skip_operand_w` | 12,633 |

**These are the language core, not movement verbs** -- expression evaluation, assignment
and operand skipping. That is itself the finding: moving the party runs *hundreds of
thousands of script instructions per second*, so movement, and by extension the rest of
the game loop, is script-driven rather than native. `0x42` is the one worth reading next:
it is not an operand-skip helper and it only appears while walking.

**Not established:** which primitives are combat, magic or party verbs. Those fire once
per event, so a call-count diff across walking cannot see them; it needs a diff taken
across the specific action, and the attack UI is mouse-driven (T29c).

**Evidence:** signatures generated mechanically from the listing by the same pass that
wrote the annotations; the walking attribution is `.ish/t11p-walk.json` cross-referenced
against the table read from the static image.

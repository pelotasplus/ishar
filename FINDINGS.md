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

### 4.9 What the splash sequence actually does, file by file

Traced from a cold boot with `tools/gdbtrace.py --drive english` (T08). Wall times
are from one clean run; they vary, the order does not.

| t | file | what is on screen |
|---|---|---|
| 0.3s | `START.STP` | launcher; setup//config blob, read before any graphics |
| 3.5s | `blancpc.io` | white/blank frame -- the screen clear between stages |
| 7.7s | `MAIN.IO` | **the script program itself** (section 7); everything after this is driven by VM bytecode, not by executable code |
| 14.5s | `findfirst main.io`, `findfirst mcave.io` | directory probes, not loads -- how the game checks what is installed |
| 14.8s | `logo.IO` | Silmarils publisher logo (`captures/t08-silmarils-logo.png`) |
| 29.8s | `presen.IO` | Ishar title card -- "LEGEND OF THE FORTRESS" over the archway |
| 60.8s | `preson.IO` | second presentation stage |
| 79.5s | `presti.IO` | title lettering; the 4bpp dithered asset from 3.14 |
| 85.4s | `iboishar.IO` | last asset before the menu |
| ~88s | `auteur.IO` | credits card |
| after | *(nothing)* | **the language menu costs 0 file calls** -- it is script in `main.io`, already resident (6.9) |

Two things worth keeping from this:

**CORRECTED: the gaps are not a timed show, they are the game waiting for input.**
The paragraph that stood here read the 10-second gap between `logo.IO` closing and
`presen.IO` opening as the logo being *displayed* for ten seconds. It is not.

Measured without any breakpoint, by screenshotting once a second and logging frames that
change by more than 25% (`tools/t42-timeline.py`):

| run | transitions in ~150s |
|---|---|
| no input sent | **one**, at t=4.0s, then nothing |
| Escape/Space/Kp1 once a second | 4.0s, 42.6s, 43.9s, 60.9s, 62.2s, 94.3s, 95.6s |

Left alone the sequence **stops after the first frame and stays there** -- the same
behaviour seen independently in T37c, where the Silmarils logo sat unchanged for 100
seconds until a key was sent. So each stage is gated on a keypress, and the wall times in
the table above are an artefact of two things stacked: the tracer stopping on every DOS
file call, and the tracer's nudge interval deciding when each stage was allowed to end.

Note the transitions come in pairs about 1.3s apart -- 42.6 + 43.9, 60.9 + 62.2,
94.3 + 95.6 -- which is a clear-then-draw, matching `blancpc.io` being the "screen clear
between stages".

**What this means for recreating the sequence:** the asset order is right and is the
useful part; the timings are not a property of the game and should not be reproduced. A
faithful recreation needs the *input model* instead, and that is not yet established --
specifically which key advances which stage, and whether any stage has a timeout (the
intro is reported to loop back to the menu if left alone, so at least one probably does).

**Evidence:** two runs of `tools/t42-timeline.py`, one silent and one driven, on an
emulator started without GDB; corroborated by the unattended 100s stall in T37c.

**The menu has four entries, and the script says four.** The screen shows
`1 - ENGLISH / 2 - FRANCAIS / 3 - DEUTSCH / 4 - ITALIANO`
(`captures/t08-language-menu.png`). Independently, the menu script at `main.io` offset
17436-17476 contains five `vm_op_jump_word` (opcode 0x0a) instructions whose
displacements 0x28/0x20/0x16/0x0c/0x02 resolve to 17480, 17482, 17482, 17482,
17482 -- **four converging on one address**, the shape of a four-way switch, plus
one lead-in. Four cases, four languages, arrived at from two directions.

**Evidence:** the trace tables in `.ish/t08-*.json`; the jump targets computed from
the handler's own instructions (`lodsw / inc si / add si,ax`, so target =
opcode+4+disp), now annotated as `vm_op_jump_word` at `seg_0000:273f`.

### 4.10 The full load order, menu to first gameplay frame (T08)

The 34 files a cold boot opens on the way into the game, in order, English run:

`START.STP`, `blancpc.io`, `MAIN.IO`, `logo.IO`, `presen.IO`, `preson.IO`,
`presti.IO`, `iboishar.IO`, `auteur.IO`, `souris.IO`, `objet.IO`, `gerdep.IO`,
`frise.IO`, `EN1.FIC`, `TAB1.FIC`, `param.IO`, `EN1.FIC`, `CONT1.FIC`, `geren.IO`,
`affobj.IO`, `encont.IO`, `dplt.IO`, **`messagee.IO`**, **`sose.IO`**, `scomb.IO`,
`buste.IO`, `bormin.IO`, `kiriela.IO`, `samb.IO`, `plaine.IO`, `fond.IO`,
`rplaine.IO`, `arbre.IO`, `lacustre.IO`

Three phases are visible in it:

1. **Splash** (`START.STP` .. `auteur.IO`) -- see 4.9. Ends at the language menu,
   which costs no file calls of its own.
2. **Engine setup** (`souris.IO` .. `dplt.IO`) -- mouse, objects, the palette bank
   `geren.io` (3.9), the object table `affobj.io` (section 8), and the world map
   `CONT1.FIC`. `EN1.FIC` is opened **twice**, before and after `param.IO`.
3. **The scene** (`buste.IO` .. `lacustre.IO`) -- portraits, then the outdoor
   assets: `plaine` (plain), `fond` (backdrop), `arbre` (tree), `lacustre`
   (lakeside). These are the first frame of Fragonir
   (`captures/t08-english-gameplay.png`).

**The per-language diff is two files.** An English run and a French run open 33
files each and differ only in `messagee.IO`/`message.IO` and `sose.IO`/`sos.IO`
(FORMATS 10.1). Nothing else is re-read for the language, which is consistent with
6.9: the menu itself is script in `main.io` and selecting a language reads nothing.

**Evidence:** `.ish/t08-english-final.json`, `.ish/t08-french.json`; both runs
driven by `tools/gdbtrace.py --drive {english,french}` from a cold boot and both
ending in gameplay, verified by the panel match in `tools/ish boot`'s `in_game()`
and by screenshot.

### 4.11 The launcher's setup screen, and how to reach it (T09c)

It exists, it is reachable, and it is titled **"SILMARILS SETUP — by Julien Pierre"**
(`captures/t09c-setup-screen.png`). Three actions -- `PLAY`, `SAVE SETUP`, `QUIT` --
over five fields, with `Use ^ v <- -> to select options, ENTER to validate.`

**How it is reached.** `load_settings` (`seg_13d7:0e96`) opens `START.STP`; at
`seg_13d7:0e9f` a `jnb` skips past `jmp 0fde`, and `0fde` is the failure path that
sets `settings_invalid`. So the screen appears whenever the file is missing,
unreadable, or fails the key-letter check (FORMATS 2).

It was reached **without touching the game's file**, by patching the two branch
bytes at runtime:

    tools/ish start --gdb --pause
    tools/ish poke 1554:0e9f 9090      # `jnb +3` -> two NOPs, so the jmp always runs
    tools/ish go

`1554` is `seg_13d7` at runtime (load `017d`). The patch lives in memory only; the
shipped `START.STP` is byte-identical afterwards. Note `poke` takes the **runtime**
segment while `dis` takes the listing one.

**The defaults**, which is what the screen shows once `settings_invalid` is set:
VGA, joystick 0, mouse Yes, QWERTY, PC Speaker.

**What the UI confirms about FORMATS 2.** The enumerations are listed on screen, in
order, which names the letters the parser matches:

| field | choices, in order | letters from the parser |
|---|---|---|
| SOUND (`captures/t09c-sound-choices.png`) | PC Speaker, Ad Lib, Sound Blaster, Sound OFF, Sound Galaxy | `I`=0 `A`=1 `B`=2 `N`=3 `G`=4 |
| KEYBOARD (`captures/t09c-keyboard-choices.png`) | AZERTY, QWERTY, QWERTZU | `A`=0 `Q`=1 `Z`=2 |
| JOYSTICK | 0, 1, 2 | digit, range-checked against 3 |

All five sound values and all three keyboard values match the parser exactly, from
a completely independent direction. Two small corrections: the third layout is
**QWERTZU**, not QWERTZ, and `I` is the **PC speaker**, which the format table left
unnamed.

Three more things the screen says:

- **VIDEO is displayed but not selectable.** Up and Down step PLAY / SAVE SETUP /
  QUIT / JOYSTICK / MOUSE / KEYBOARD / SOUND and skip over VIDEO entirely. It is
  shown as VGA and cannot be changed -- consistent with a VGA-only release, though
  the parser still decodes CGA/EGA/Hercules.
- **`R` and `P` never appear.** Consistent with FORMATS 2: `R`'s value is never read
  and the port is not surfaced to the user.
- **The suggested keyboard is AZERTY**, the studio's own layout, while the shipped
  `START.STP` says `KQ` = QWERTY.

**Evidence:** the three captures above, taken from a live run patched as shown;
`START.STP` verified unchanged (`RBVVSAP1J0M1KQ`) after the session.

### 4.12 Is FORMATS.md good enough to build from? Mostly, and here is the number (T36)

The question was whether 1,700 lines of format prose actually lead anywhere. The test:
a decoder written **only from FORMATS.md**, run over the whole corpus, and checked
against what the emulator puts on screen.

**Level 1 -- the container. 98/98.** `java/IsharCorpus.java` decodes every `.io` file
in the game: 97 in mode `0xa0` (bit-packed LZ77) and one, `blancpc.io`, stored,
1,583,646 bytes of payload in total. No failures.

That alone proves little -- an LZ decoder can produce garbage without throwing. So:

**Level 2 -- an independent implementation. 98/98 byte-identical.** Every payload was
compared against `tools/io.py`, written separately from the disassembly. All 98 agree
byte for byte, none differ, none error. Two implementations can still share a mistake,
which is why there is a level 3.

**Level 3 -- the machine.** The live framebuffer at `0xA0000` was dumped while the
Silmarils logo was on screen and searched across all 98 decoded payloads. **Exactly one
matched**: `logo.io`, and no other asset contained any of the probe runs.

The layout was then measured rather than assumed, from where the matching runs landed:
adjacent screen columns are 1 byte apart in the file, adjacent rows 144 -- so 8 bits per
pixel, 144-byte stride. The header that predicts that geometry is at offset 1856,
`mode = 0x14`, `144x118`, pixels at 1864, which is exactly what FORMATS 3.10 says a mode
`0x14` record looks like.

Comparing all of it against VRAM at its measured origin (screen x=84, y=11):

| | |
|---|---|
| opaque pixels compared | 12,875 |
| identical to the framebuffer | **12,850 = 99.81%** |
| index-0 pixels skipped (3.13 keying) | 4,117 |
| differing | 25 |

The 25 are not scattered: they fill one **13x13 square** at x 91-103, y 100-112, and
their screen values (129-141) do not overlap the sprite's own range (21-31) anywhere.
That is a second sprite composited on top -- the animated sparkle by the blue gem. It
moved between two captures taken 15 seconds apart, which is the confirmation.

**So the honest scoreboard:**

- container + LZ: **proven** on 100% of the corpus, two ways.
- 8bpp sprite records, geometry, and index-0 keying: **proven against the machine**, with
  every differing pixel accounted for.
- 4bpp: **now machine-verified too, and it corrected the spec** -- see T36b below and
  FORMATS 3.13b. Superseded text follows for the record:
- ~~4bpp: cross-validated, not machine-verified.~~ The Java reader and `tools/ioscan.py`
  agree on the 4bpp assets, but agreement between two readers is level 2, not level 3,
  and 4bpp is where every historical bug in this project lived (the palette group, the
  transparency over-generalisation, the nibble order). It is the majority of the art.

**Evidence:** `java/out/corpus.csv`; the Python/Java comparison; `tools/t36-fbmatch.py`
and the numbers above, from `.ish/fb.bin` captured live while `captures/t36-logo-verified.png` was on screen.

### 4.13 The 4bpp check, and the rule it overturned (T36b)

`buste.io`'s portrait -- mode `0x10`, 64x36, at payload offset 6986 -- compared against
live VRAM with the party panel on screen:

| | |
|---|---|
| nibble != 0 | **1233 / 1233 = 100.0000%** identical |
| nibble == 0 | 1071 pixels, **0** identical |

So the decoder written only from FORMATS.md is exactly right on every pixel the game
drew, and every nibble-zero pixel shows the frieze behind it (values 177-181 =
`frise.io`'s base 176). **Mode `0x10` keys nibble 0**, which FORMATS 3.13 explicitly
denied. Details and the consequences are in FORMATS 3.13b; the short version is that the
test is on the *nibble*, before the group base is added, and that `expand_4bpp` at
`seg_0e97:0ad1` cannot be the routine that drew it (T36c).

Two things confirmed on the way, both from directions that did not know the answer:

- **`word3 >> 4` is the palette group.** The sprite's `word3 = 0x00d0` predicts group 13,
  base 208. A reverse search -- take the screen bytes, subtract a candidate base, check
  every result is 0..15, repack two per byte high-nibble-first, and look for that in the
  decoded payloads -- recovered base 208 for `buste.io` and 192 for `frise.io` without
  being told either.
- **The outdoor viewport is not a blit.** No asset matches the 3D view at either depth,
  over 1,517 probe runs. The UI panel matches immediately. That is T11p's finding arriving
  from a different direction: verify against the panel, never the viewport.

**Evidence:** `.ish/fb3.bin` captured live in Fragonir (`captures/t36b-panel-verified.png`); the per-nibble split above.

### 4.14 T38: checking the `main.io` listing against the running VM

`vmdis --stats` says 97% of `main.io` "decoded as instructions". That number cannot
fail -- 219 of 231 byte values are valid opcodes, so a linear walk scores ~97% from any
offset. `tools/vmcheck.py` is the check that can: `vm_run` (`seg_0000:26eb`) is
`sub ah,ah / lodsb`, so at its entry `DS:SI` is the address of the next opcode -- an
instruction boundary by definition. Sample it live, and ask how many vmdis agrees with.

**It immediately found a real bug, and one we caused.** `vmdis` builds its instruction
table from `ishar-listing.txt` with `^seg_0000:(addr)\s+([a-z][a-z0-9]*)`. That pattern
also matches a **label** line -- `seg_0000:273f vm_op_jump_word:` matches with `vm` as the
"mnemonic", because `_` ends the character class -- and the label precedes the real
instruction, so `CODE.setdefault` kept the label and discarded the `lodsw`.

Every handler that was given a name in `ishar.chani` thereby lost its operand width.
`vm_op_jump_word` reported `operands -` and two of them decoded one byte apart. So
*annotating the database silently degraded the disassembler*, and the headline percentage
did not move when it was fixed -- 97% before, 97% after -- exactly as designed.

**Result after the fix, gameplay phase:** 34 of 34 sampled `DS:SI` values are instruction
boundaries, **100.000%**. Before the fix the same check failed at offset 3352, which is
now a boundary.

**What is not yet established.** The Done-when asks for three phases and thousands of
samples; neither is met:

- Sampling is slow (a stop is a pause/resume; ~0.3 useful samples/second) and it
  **saturates**: the game idles through the same statements, so 140s yields the same 34
  distinct offsets as 45s. More time does not buy more coverage; different *activity*
  would.
- `vm_run` produced **no** samples during the intro or a cold boot in 160s, so those
  phases are untested rather than passing.
- An early boot run reported failures at offsets 103 and 150, which are still not
  boundaries. That measurement used a weaker anchoring method (below) and is not
  trustworthy on its own -- but vmdis independently emits `db` bytes at 88, 95 and 151,
  which is its own signal that the region is misaligned, and offsets under ~160 are where
  `main.io`'s catalogue lives (T11e). A catalogue decoded as instructions would look
  exactly like this. **Open question, not a passed check.**

**A retraction from this work.** Two consecutive runs reported live scripts executing
inside `frise.io` and then `gerdep.io` -- which would have been a direct answer to T37,
whose blocker is that embedded scripts have no known entry point. Both were wrong. The
anchoring matched a 24-byte run and took the first asset alphabetically that contained
it, without checking uniqueness *across* assets. Re-tested at 24, 64 and 128 bytes against
all 98 assets, every sample matched `main.io` and nothing else. `vmcheck.py` now requires
a 64-byte run unique within `main.io` and absent from every other asset.

**Evidence:** `.ish/vmcheck-gameplay.json`; the fix in `tools/vmdis.py`; the cross-asset
ambiguity test.

### 4.15 What actually draws the game screen

Probing a live gameplay framebuffer region by region and matching each run of pixels back
to a decoded asset (8bpp directly, 4bpp by subtracting a candidate base and repacking):

| screen region | drawn from | depth / palette base |
|---|---|---|
| the 3D viewport | `fond.io`, `plaine.io`, `arbre.io` — **no asset matched at the time**, which was the search and not the format (4.15d) | 4bpp, base 16 for `plaine.io` |
| right-hand panel (compass, dial, DISK) | `frise.io` | 4bpp, base 208 (group 13) |
| ACTION / ATTACK bar | `frise.io` | 4bpp, base 192 (group 12) and 176 (group 11) |
| LIFE bars | `frise.io` | 4bpp, base 192 |
| character portraits | `buste.io` | 4bpp, base 208 (group 13) |

**So the whole UI chrome is one asset.** `frise.io` supplies the right panel, the action
bar and the life bars, drawn at three different palette bases -- the same sprite data
recoloured by group, which is what the `word3` base is for (3.13c). Portraits come from
`buste.io`, which holds 27 sprites of 64 pixels wide; the one verified byte-for-byte
against VRAM is at payload offset 6986, mode `0x10`, 64x36, `word3 = 0x00d0` -> base 208,
drawn at screen (0, 147) (3.13b).

~~**The viewport is the exception and it is not a blit.** No asset matches it at either
depth, over 1,517 probe runs in T36 and 72 more here.~~ **Half struck.** The viewport *is*
a blit -- 1:1, established in 4.15c -- and its sprites **do** appear verbatim in video
memory. Three `plaine.io` sprites were matched at **100%** of their opaque pixels in one
frame (4.15d). What defeated the earlier search was the search, not the format: it looked
for whole assets and for contiguous runs across masked sprites, where the background shows
through the holes. It is composed by its own routines
(`viewport_row_loop`, `viewport_expand_4bpp`, `viewport_fill_rect` -- FORMATS 3.13d) which
walk source and destination with independent per-row steps, sampled live at 15 and 321. A
destination step of 321 on a 320-wide buffer shears every row one pixel sideways; that is
where the perspective comes from, and it is why viewport pixels can never appear verbatim
in any file.

**How a frame reaches the screen.** Everything is drawn into an offscreen buffer at
segment `e000` and copied to `a000` by `blit_to_screen` (`seg_0e97:0192`, `rep movsw`),
same offsets, rows 320 apart -- so the back buffer is 320 wide and maps 1:1 onto VRAM.

**What is still unknown:** where the *positions* come from. The portrait's screen origin
was measured, not derived; the script presumably supplies layout, which is T39b/T30
territory. And the viewport's scale factors are read from `cs:[002c]`/`cs:[002e]` at
runtime -- what computes them is not known.

**Evidence:** region probe against `.ish/fb3.bin` (a live gameplay frame); the
byte-for-byte portrait comparison in FORMATS 3.13b; the blit source/destination read at a
breakpoint on `blit_to_screen`.

### 4.16 Attributing routines to game actions, now that the mouse works (T29c)

With mouse input delivered (T29c3), actions can be performed and the emulator's per-function
call counts diffed around them. A plain before/after diff is useless -- the interpreter runs
flat out while the party stands still, so **264 functions move during an idle window** -- so
`tools/t29c-action.py` measures an idle window and an equal action window and reports the
excess.

**Validation:** the ACTION menu diff independently re-finds `vm_op_draw_menu` (opcode
`0x4b`, 159 calls, zero while idle), which T29c had established by a different route.

| action | routines that ran only during it |
|---|---|
| ACTION menu (F1) | `ui_menu_draw_loop` `35ae` (4,248), `vm_op_draw_menu` `3a84` (159, opcode `0x4b`) |
| MAP from the menu | `map_decompress_inner` `7ceb` (15,963), `7cbf` (5,999), `7ce9` (5,272) |
| any mouse click | `ui_click_dispatch` `42f5`, with `01a8` and `0008` in lockstep |
| portrait click | `party_member_select` `9386` (28), `9396`, `9375`, `8e2b` |

Two of these are worth more than their counts. **`ui_click_dispatch` is not
action-specific** -- it fires on all four different clicks and never while idle, so it is
the click path itself, which makes it the hook for driving any UI action. And **choosing
MAP decompresses an asset** (the `0x7cxx` range is the container decoder, FORMATS 3.2)
rather than drawing something resident.

**What this does not yet do** is attribute ten *VM primitives*. Almost everything the
diffs surface is an engine routine rather than a statement handler: a UI action costs one
or two script statements and thousands of engine calls, so the primitives are buried under
the noise floor. Only `0x4b` and `0x08` mapped to opcodes across four actions. Combat
specifically produced no strong signal -- clicking ATTACK with no enemy adjacent changes
almost nothing, which is a fair result rather than a failed measurement.

**Evidence:** `tools/t29c-action.py`, idle-vs-action windows of equal length; the
validation against the independently-known `0x4b`; `.ish/t29c-*.json`.

### 4.17 First contact with the game's own rules (T29f)

With the mouse working, the party can be driven into the world. Three things came out of
one attempt to start a fight, none of them previously recorded.

**NPCs talk when you walk into them.** The figure standing in the Fragonir starting scene
is not a monster. Walking four steps forward brings up a text panel over the bottom third
of the screen (`captures/t29f-npc-dialogue.png`):

> WARM TEAR! TO THE SOUTH, IN ANGARAHN COUNTRY, THERE IS A NICE LITTLE VILLAGE, ITS
> TAVERN, 'THE THIRSTY BARBARIAN', IS KNOW MILES AROUND.

So world text is delivered by proximity, not by a menu verb, and it names two places --
**Angarahn** and the tavern -- that are leads for the map work.

**ATTACK is two-step.** Clicking a character's ATTACK button alone only dismisses whatever
panel is open. Clicking ATTACK and *then* clicking a target in the viewport is what acts.

**Attacking a friendly NPC resets the party.** The second click produced a full-screen
demon frame -- a horned face over a glowing orb full of tiny falling figures
(`captures/t29f-consequence-demon.png`) -- which waits for a mouse click, not a key, and
then returns the party to its **starting position**. Ishar is known for punishing murder;
this is that system, observed. **That frame is `dead.io`**, decoded and matched
64,000/64,000 against VRAM while it was on screen (4.20).

**Two opcodes attributed** by call-count diff against an idle window of equal length:

| opcode | handler | evidence |
|---|---|---|
| `0x15` `vm_op_15` | `seg_0000:28a9` | **7,805 calls** when ATTACK is clicked with a target ahead, 0 idle -- the largest mover of any action measured. Not combat-exclusive (903 in another baseline), but driven ~9x harder. Named `vm_op_attack_swing` at first and **renamed**: it occurs 8x in `affobj.io`, which never fights (FORMATS 8.0b) |
| `0x57` `vm_op_consequence_event` | `seg_0000:4b8f` | 96 calls at the moment of the demon frame, 0 idle, and absent from every other action measured -- menu draw, MAP, portrait select, click on empty ground |

**What is still not done:** T29f asked for a monster in the viewport and a LIFE bar
changing. Neither happened -- no LIFE bar moved, and the only creature encountered was
friendly. Wandering to find a monster failed too: six forward steps per turn for twelve
turns ended against a hedge with the frame changing 0.0-0.3%, so terrain blocks movement
and blind exploration is not a method.

**Evidence:** `tools/t29c-action.py` idle-vs-action windows; the three captures above.

### 4.17b The game's verb list, and what `encont.io` is not

**ACTION opens a ten-entry verb menu** (`captures/t29f-action-menu.png`), which is the
whole of the game's non-combat interaction:

| | |
|---|---|
| **GIVE ITEM**, **GIVE MONEY** | transfers, so NPCs take payment |
| **KILL**, **DISMISS**, **RECRUIT** | party management -- the party is assembled from NPCs met in the world, and disbanded the same way |
| **PICK LOCK** | a skill check on doors or containers |
| **ORIENTATION** | **a navigation readout, not a facing control.** It reports the region lying in the direction the party faces -- at `(17,53)` in ANGARAHN it answers `E : LOTHARIA` (`captures/t11g3g-orient.png`). One line, one direction, so there *is* a facing; this verb reads it out rather than setting it, and how facing is set is still unknown |
| **FIRST AID** | healing outside magic |
| **MAP** | the player-facing map, which is `map.io` (FORMATS 3.12) |
| **EXIT** | closes the menu |

`RECRUIT` and `DISMISS` are the mechanical answer to how a party of five is built.

**The verbs are modal, and that matters for an input model.** Selecting `PICK LOCK` arms
it -- the pointer becomes a lockpick -- and until it is used or cancelled **the arrow keys
do not move the party**. The same two-step shape as ATTACK (4.17): choose the verb, then
choose the target. A rewrite needs an explicit "pending verb" state, not a fire-and-forget
menu.

**`encont.io` is not the encounter trigger for anything the player does.** Polling
`vm_run` while driving the game attributes execution to assets; across every window tried,
`encont.io` appears in none:

| window | attributed samples | `encont.io` |
|---|---|---|
| idle, walking, turning, approaching an NPC (T44) | 1,400-2,400 each | 0 |
| killing an NPC, through the party-wipe screen | 6,552 | 0 |
| **144 steps across varied terrain**, 12 distinct cell values | **18,863** | 0 |
| the ACTION menu, including ORIENTATION, MAP and KILL | 4,888 | 0 |

The 144-step walk is the decisive one: if encounters were driven by movement or by the
terrain walked over, that window would have caught them. `encont.io` executes exactly once,
in the 0.3s burst at 123.0s where ten scripts start together as the game proper begins, and
then waits. Whatever wakes it is not movement, not terrain, not a menu verb and not combat
against an NPC.

Remaining candidates, none tried: a region change (FORMATS 3.12 -- the six grids are not
tiles, so region changes are scripted), entering a building, and time passing. See T44.

**Evidence:** `tools/t44-when.py` windows, each filtered to samples where `CS == load` and
`IP` is inside `vm_run`'s fetch loop; the ACTION menu capture.

### 4.19b The world has twenty-one named regions, and they live inside the grids

The panel's top-right caption names where the party is. Walking east from the starting
cell it changes from **FRAGONIR** to **ANGARAHN** -- with the same `cont1.fic` still
resident and byte-identical. **So a "region" is a named sub-area of a grid, not a grid
file.** Six grid files and twenty-one regions; they are different things, and the earlier
assumption that a region change means a new `cont*.fic` was wrong.

*(That caption also corrects a misreading: the starting region is FRAGONIR, not "Dragonia".
It was read off a screenshot at 640px and taken as settled. The bytes say otherwise, and
`fragorn.io` is sitting in the asset list next to it. Renamed throughout.)*

**The gazetteer is bytecode, not a data table.** The names sit in `frise.io` (the script
that draws the panel, 4.15) and again in `gerdep.io`, as a run of fixed 17-byte statements,
each `0a <word> 00 1e 04 "NAME" 00 16 ..` -- an if/else-if ladder, with the word operand
decreasing by exactly `0x11` per entry, i.e. the distance to the end of the ladder:

| | | | |
|---|---|---|---|
| 1 FRAGONIR | 6 FIMNUIRH | 11 BALDARON | 16 ULDONYAR |
| 2 ANGARAHN | 7 ARAGARTH | 12 VARGAEON | 17 VALATHAR |
| 3 OSGHIROD | 8 KANDOMIR | 13 ZENDORIA | 18 ELWINGIL |
| 4 LOTHARIA | 9 SILMATIL | 14 URSHURAK* | 19 FHULGROD |
| 5 RHUDGAST | 10 URSHURAK | 15 HALINDOR | 20 **ISHAR** |
| | | | 21 **L'OCEAN** |

(`gerdep.io` carries all 21 including `ISHAR` and `L'OCEAN`; `frise.io`'s list ends at
`FHULGROD` and then `OCEANO`.) The last two matter: **the ocean is a region**, which is
what the impassable `0xCC`/`0xCD` blobs are (6.7b), and **ISHAR is a region**, which is the
fortress of the title -- `cont5` is almost entirely one walled structure.

The in-game text agrees: the NPC's line, "TO THE SOUTH, IN ANGARAHN COUNTRY, THERE IS A
NICE LITTLE VILLAGE, ITS TAVERN..." (4.17) names a region from this list, and the French
original names a tavern "LE RELAIS DE FRAGONIR".

**The region id is a VM global: byte `0x3EAC`.** The caption is drawn by a **switch** --
statement `0x2f`, whose encoding this found (FORMATS 7.2g): an expression for the selector,
a case count, a bias word, then one signed displacement per case. In `gerdep.io` at 8829
the count is `0x14` (21 cases) and each arm prints one name, so the ladder is a switch on a
single variable. Its selector expression is `1e ac 3e` = `vm_op_load_byte_global 0x3eac`.

Read live at `es:[ss:[0bf6] + 0x3eac]` it is **0 in FRAGONIR, 1 in ANGARAHN, 2 in
OSGHIROD** -- the index into the name list above. `tools/region.py` reads it, and that beats
scraping the caption.

**It is not the cell value.** Walking a row eastwards the region flips FRAGONIR -> ANGARAHN
between **column 45 and column 46**, at row 11 and again at row 12, and the cells on both
sides are `0x00`. Two identical adjacent cells in different regions rules the grid out as
the source.

**A script writes it, and the rule is hand-written conditions.** A `MEMORY_WRITE`
breakpoint on the region byte catches the change at cell `(10,46)` going east and `(10,45)`
going west, with `IP` inside `vm_run`'s fetch loop -- so the writer is bytecode, and `DS:SI`
names it: **`gerdep.io` around offset 7243**. Read with the operator table (6.1b) it says
exactly what the boundary measurement said:

```
1f 38              eval( sequence(
  1e 7d 13           global[0x137d]      the party's column
  52 00 2e           < 46
  40                 push
  1e ac 3e           global[0x3eac]      the region id
  4a 00 01           == 1
  42                 &
3a  /  14 ..       )) then jump_if_zero
```

`if (column < 46) && (region == 1)`. The next test along is narrower still:

```
(row == 25) && (column == 60) && (region == 1)
```

-- a single named cell, not an area.

**So there is no formula and no lookup table.** Region membership is a list of explicit
coordinate comparisons in `gerdep.io`'s bytecode, mixing half-plane tests with single-cell
ones. A rewrite either ports those conditions or re-derives an equivalent set by walking.

**Evidence:** `tools/t11g3f-writer.py` -- a MEMORY_WRITE breakpoint on the region byte,
believed only at stops where the value actually changed, with `DS:SI` attributed to an
asset; the boundary independently measured at rows 10, 11 and 12 **before** the bytecode was
read, which is the prediction this rule has to match and does.

**`ss:[0x0902]` is a shared string workspace, not a region variable.** It holds the region
name at rest, which makes it a cheap readout, but during a scene load it carries
`main.io`, `EN1.FIC`, `foret.io` in turn, and during dialogue it carries message text. Any
probe reading it has to check the value spells one of the 21 names before believing it --
`tools/t11g3f-lattice.py` does. This is the same trap as the memory-write breakpoint in
CLAUDE.md: a buffer you have only seen holding one kind of value is not a buffer that only
holds that kind of value.

**Buildings are the blocked singletons.** Walking to `(17,53)` puts a large wooden double
door on screen (`captures/t11g3e-at1753.png`). Its cell neighbours `0xF0` to the west and
`0xEB` to the north both refused entry -- both are values that occur once or twice in the
whole grid, in a cluster of such values around rows 14-18, columns 52-59. That cluster is
the village the NPC describes, and each rare value is one building. Clicking the door does
nothing, and no new script runs (4,323 samples), so entry needs something else -- the
ACTION menu has **PICK LOCK**.

**Not all low values are walkable.** `0x0A` refused a move, so `value < 0x40` is not a
walkability test. **And the split is not per value either** -- the same value blocks in one
place and not another because an NPC may be *standing* there (4.15i). Terrain and occupancy
are separate layers.

**There is a "bounce back to the start" event, and the game is gated by it.** Stepping
north from `(13,57)` does not move the party: after a few attempts the scene reloads --
`main.io`, `EN1.FIC`, `foret.io` pass through the string workspace -- and the party is
returned to its starting cell `(11,29)`, still in `cont1`, still FRAGONIR. Reproduced
twice, and again walking west from `(39,25)` in OSGHIROD. That is the **same outcome as the
murder consequence** (4.17), which also returns the party to its starting position, so the
two plausibly share one mechanism.

So the world is larger than the party may walk: three separate attempts to leave the
opening area ended back at the start. That is a gate, not terrain -- the cells involved are
ordinary `0x00` -- and it explains why every wander-based experiment in this project has
stayed within a dozen cells of the start. No new script runs while it fires (1,772
attributed samples, no `encont.io`).

**Evidence:** the panel caption across two positions with `cont1.fic` verified resident and
unchanged; the name run extracted from both assets' decoded bytes; the DGROUP diff between
two cells in each region (`tools/t11g3e-region.py`); `tools/walkto.py`'s refusal log.

### 4.19c Getting into a building: four ways that do not work

The village in `cont1` at rows 14-19, columns 52-59 is a cluster of one- and two-cell
values -- `0xEB`, `0xED`, `0xEF`, `0xF0`, `0xF2`, `0xF5`, `0xF6` -- each a building, all
impassable. Standing at `(17,53)` puts a wooden double door on screen
(`captures/t11g3g-door.png`). None of these opens it:

| attempt | result |
|---|---|
| walk into the building cell | refused, the coordinate does not change |
| click the door in the viewport | nothing; 4,323 attributed samples, no new script |
| **ACTION -> PICK LOCK**, then click the door | the verb arms and fires, the door does not open; 2,212 samples, no new script |
| the panel's four compass buttons | no movement at all |

**And the party then cannot move in any direction.** After the PICK LOCK attempt, all four
arrow keys and all four panel buttons are refused at `(17,53)` -- including the direction it
walked in from. The ACTION menu still opens, so the game is responsive; the party is not.
This has now happened twice at a village cell beside a building, and once it preceded the
UI degrading (a portrait losing its frame). Whether it is a script gate, an un-cleared modal
state, or something this harness does is **unresolved** -- and it is the reason T11g3g is
parked rather than continued.

What this does settle: entry is not a movement, not a viewport click, and not PICK LOCK
alone. The remaining candidates are a verb applied while facing the right way (facing is
readable via ORIENTATION but not yet settable), a key this project has not tried, or a
precondition the party has not met -- the world is gated (6.7b) and the village may be
behind that gate.

**Evidence:** the four attempts above, each polled with `tools/t44-when.py`; the captures
`t11g3g-door.png`, `t11g3g-picklock.png`, `t11g3g-picked.png`, `t11g3g-orient.png`.

### 4.19d The map is a VM variable, and cell-to-sprite is a program, not a table

T11g3d set out to match cell values to sprites by walking a line and capturing the viewport
at each cell. **That does not work**: the viewport holds many cells at once, so two cells
with the same value gave completely different pictures. The label was never isolating the
thing being labelled.

Tracing the consumer instead answers a better question. Arming a `MEMORY_READ` breakpoint
on one grid cell and walking the party onto it gives, reproducibly on two cells, **three
reads, all at `seg_0000:7153`** -- inside the VM expression evaluator's loop
(`call 069ab / jmp 7150`). No native rendering routine touches the cell at all.

*(A second site, `seg_0000:93b5`, is the AdLib sequencer whose stream pointer wanders
through that memory and reads a zero; and `seg_0000:3d64` is `wait_loop`, the idle spin
that any pause reports. Both are filtered. Two runs that produced only `wait_loop` stops
were discarded rather than counted -- a memory breakpoint has no IP to check against, so
the known phantom site is the only guard there is.)*

**So the map is a VM global.** Everything lines up on the base pointer `ss:[0bf6]`, which
reads `126b:02a0` = linear `0x12950` in two separate sessions:

| | global offset | |
|---|---|---|
| the map grid | **+0x0080** | 4,860 bytes, `cont*.fic` verbatim |
| party row | **+0x137C** | immediately after the grid -- which is what 6.7b's "grid_end" adjacency actually is |
| party column | **+0x137D** | |
| region id | **+0x3EAC** | 0..20 into the 21 names (4.19b) |

That reframes the "grid_end" coincidence: the row and column are not *next to* the grid by
luck, they are the next fields of one structure in the script variable area. And it gives a
rewrite the honest shape of the thing -- the world state is **one flat byte array the
scripts index**, not an engine structure with an API.

**The consequence for a rewrite is the finding.** There is no cell-value-to-sprite table to
extract, because the decision is made in bytecode. A cell value means whatever the scene
script does with it, so the choices are to port that bytecode or to reimplement the
behaviour by observation. That also explains 6.7b's "the walked path crosses eight distinct
walkable values in eighteen cells" and why `plaine.io`/`arbre.io` run only when the view
changes (T44) -- those are the programs doing the drawing.

**The reader, and the access itself.** Widening the sample settles it. Driving the party
back and forth across a watched cell gives **95 and 51 genuine stops** on two cells, and the
single dominant site in both is `seg_0000:7153` with the script PC in **`lacustre.io` at
offset 1190-1200** -- 36 and 23 hits, against scattered singletons everywhere else.
`lacustre.io` is the *lakeside* scene script and the party is standing by the lake, so the
reader is **the scene script for the terrain it is standing on**, not one global manager.

The statement there decodes completely (FORMATS 7.2h):

```
1e                statement: eval_reset
  38              begin an expression sequence
    12 18         byte frame var 24          -- a subscript
    40            push it
    12 19         byte frame var 25          -- the other subscript
    26 80 00      global[0x0080 + index]     -- the map
  3a              end the sequence
```

**`0x26` is an indexed global load and the VM has real arrays.** `vm_index_byte` reads an
array's descriptor from the bytes immediately *below* its data: a dimension count at
`base-1` and a stride word per dimension below `base-2`. Read live for the map, the count is
**1** and the stride is **90** -- so the map is declared `map[54][90]` and the access is
`map[row][col]`. The stride the game stores is the one the grid geometry independently
requires, which is the check.

That retires the guess in the previous paragraph: `gerdep` was the favourite on etymology
and call count, and the evidence names `lacustre.io`.

**A walkability correction.** `0x0A` refused a move at `(14,29)` (4.19b) and permitted one at
`(11,40)` in this session. **So blocking is not a function of the cell value alone** -- which
follows from the above: a script decides, and it can consult anything.

**Evidence:** `tools/t11g3d-reader.py` and `t11g3d-who.py`, two watched cells, three genuine
reads each with phantoms filtered; the base pointer read in two sessions; the failed
viewport comparison in `captures/t11g3d/`.

### 4.15b An asset can hold several sprite chains, and the panel is in the second one

Looking for the sprite that draws the right-hand panel found it **at `frise.io` offset
51456** -- past the end of the chain `tools/ioscan.py` reports, which stops at 42514.

**The sprite.** 32 x 126, mode `0x10`, palette base 208, drawn at screen **(288, 0)** --
the full-height right edge of a 320-wide frame. Matched against live video memory:
**97 of its 126 rows are pixel-perfect**, and every mismatched row is somewhere the game
composites on top of it:

| rows | what covers it |
|---|---|
| 2-9 | the region caption -- `FRAGONIR` in this frame |
| 22-23, 33, 39-40, 50-51 | the compass needle and its N/E/S/W letters |
| 52-65 | the DISK button |

**The general finding is bigger than the sprite.** `ioscan.py` picks the single offset whose
chain explains the most of the file and walks only that one. `frise.io` has **five** chains:

```
14 sprites at 35964..42514     6,550 bytes    <- the only one ioscan reports
 3 sprites at 42584..43568       984
 5 sprites at 43574..46766     3,192
12 sprites at 48382..49822     1,440
12 sprites at 49944..53752     3,808         <- the panel is in here
```

46 sprites, not 14, and 29.7% of the file instead of 12.2%.

This is not peculiar to `frise.io`. Walking every chain rather than the best one:

| asset | best chain only | every chain |
|---|---|---|
| `temple.io` | 29.3% | **93.4%** |
| `objet.io` | 19.1% | **79.8%** |
| `mcave.io` | 50.8% | **77.4%** |
| `ville.io` | 41.8% | **76.2%** |
| `marchand.io` | 3.8% | 3.8% -- unchanged, so something else is going on there |

So a large part of what `FILES.md` calls unexplained is **sprites nobody walked to**, not an
unknown format. `tools/chains.py` finds them all.

**Evidence:** the panel sprite verified against live VRAM at `0xA0000` with the game in
Fragonir, 3,585 of 3,966 opaque pixels correct and every failure inside a compositing band;
chain enumeration over the assets above.

### 4.15c The viewport does not scale -- distance is a different sprite

The 3D view copies sprites into the frame buffer **1:1**. Measured at the row step both
viewport loops share (`viewport_row_step`, `seg_0e97:05f4`): the destination pointer
advances **exactly 320 per row** and the source pointer **exactly one source row**, on 30
of 30 stops across a walk.

Nothing is stretched, squashed or sheared. FORMATS 3.13d previously read one of the loop's
per-row constants as a shear "which is where the perspective comes from"; that is struck
there, and the numbers behind it were real while the reading was not.

**So an object's apparent size is the size of the sprite chosen.** `arbre.io` carries
fifteen sprites in a graded ladder rather than fifteen different trees:

```
16x15   16x27   16x43   16x47   16x65
32x25   32x40   32x62   32x71   32x101
48x38   64x67   64x72   80x128  144x83
```

A tree twice as close is a larger sprite, not the same sprite enlarged.

**Objects are clipped, not scaled, at the viewport edge.** The two draw widths seen, 17 px
and 32 px, both had a source row stride of 16 bytes -- the same 32-pixel sprite, once whole
and once cut off where it ran past the edge.

**What this means for a rewrite.** There is no projection to reproduce: pick the rung, blit
it 1:1 at its position. That is considerably less work than the perspective maths the
earlier reading implied. Which rung goes with which distance is open (T54b).

**The viewport's backdrop is `fond.io`** -- *fond*, French for background. Breaking at the
opaque expander's row step (`viewport_row_step_opaque`, `seg_0e97:0660`) and matching 48
bytes at `DS:SI` against every decoded asset names the source directly, which the
framebuffer cannot do because objects clip and overlap:

| sprite | size | seen |
|---|---|---|
| `fond.io` @1366 | 64x43 | 120 rows, widths 64 and 15 |
| `fond.io` @2750 | 64x85 | widths 64 and 15 |
| `fond.io` @5478 | 48x69 | 68 rows, widths 48 and 64 |
| `fond.io` @7142 | 96x63 | 33 rows, widths 96 and 48 |

The same sprite appearing at two widths is the edge clipping again -- @1366 drawn at 64 and
at 15, @5478 at 48 and at 64.

**And which sprites are drawn changes as the party moves.** At `(10,40)` the view is built
from @5478, @7142, @1366 and @2750; three steps north at `(12,40)` it is almost entirely
@1366.

**Splitting a frame into objects shows what `fond.io` actually is.** `BP` counts the rows
remaining for the object being drawn, so a run of stops with `BP` decreasing by one is one
object, and its first row's `DI` gives the origin (`y = DI // 320`, `x = DI % 320`, because
the blit is 1:1). One frame at `(10,22)`:

| sprite | size | drawn at | rows |
|---|---|---|---|
| `fond.io` @1366 | 64x43 | x = **47, 111, 175, 239**, and 256 clipped, all at y=83 | 43 each |
| `fond.io` @2750 | 64x85 | (96, 0) | 57 |

Those x values are **64 apart**. So the ground is *one* 64x43 sprite **tiled horizontally**,
its run starting at x = -17, and @2750 is the sky. `fond.io` is the sky and ground bands,
and they are **tiled sprites, not flat fills** -- FORMATS 3.13d called `viewport_fill_rect`
the source of "sky and ground bands", which is at best incomplete.

A rewrite therefore needs a horizontal tile offset for the ground: -17 in this frame, and
it is the obvious candidate for what makes the ground appear to move.

**`arbre.io` IS drawn, and two rungs appear in one frame.** An earlier version of this
paragraph said it had never been observed; that was true of the probes tried up to then and
is now wrong. Attributing the masked expander's source at `(13,28)` gives, in a single
frame:

| sprite | size | drawn at |
|---|---|---|
| `arbre.io` @25490 | 16x27 | (247, 61) |
| `arbre.io` @25714 | 16x15 | (256, 66) |
| `arbre.io` @12906 | 144x83 | (256, 0), clipped to 43 px/row |

Two *different* rungs of the 16-pixel-wide family on screen at once, at different heights
-- which is what a distance ladder looks like in use. The 144x83 is the big foreground
branch.

**The masked expander draws everything that needs transparency**: `main.io`'s font glyphs,
`plaine.io`'s scenery, and `arbre.io`'s trees. In the same frame it also drew `plaine.io`
@31600 (48x19 at (43,76)), @32064 (32x12 at (256,79)), @20934 (48x9 at (76,94)), @23090,
@23194, @23258.

**Still not established: which rung at which distance**, and the way it failed is worth
keeping because it separates the two instruments.

Pairing a rung with a distance needs the same object at two party positions. The breakpoint
route is unreliable frame to frame -- it slows the machine so far that a window catches
only part of a redraw: `(13,28)` gave 14 objects, the same run length at `(17,28)` and
`(14,28)` gave one and two.

The breakpoint-free route (`tools/onscreen.py`, 4.15d) then found **no `arbre.io` sprite on
screen at all** -- not at `(11,28)`, `(13,28)` or `(15,28)`, the very cell where the
breakpoint had just watched three of them being drawn, and not along column 42 either.
Lowering its probe length for narrow ragged sprites changed nothing.

**So the two instruments see different things.** A breakpoint at the row step sees
everything *drawn*; `onscreen.py` sees only what *survives* to the final frame. An
`arbre.io` tree is drawn and then covered -- by a nearer object or by a later band -- so it
never appears verbatim in video memory. That also bounds 4.15d: its seven 100% matches are
the unoccluded sprites, not an inventory of everything composited.

Anything about draw order or occlusion therefore has to come from the breakpoint, and
anything about the finished frame from the framebuffer. See T54b.

**A correction to which routine is which.** `seg_0e97:05c0`, named `viewport_row_loop` in
FORMATS 3.13d, draws the **panel** in every window sampled: 9 of 9 rows from `frise.io` at
x=272. The loop that draws the 3D view is the opaque one at `0644`/`0660`. Three loops in
`seg_0e97` share the identical row-step idiom, so finding one of them by watching writes to
the back buffer does not establish which one serves the viewport.

**Evidence:** an execution breakpoint at `seg_0e97:05f4` reading `CX`, `DX`, `BP`, `SI` and
`DI` at 30 stops (`tools/t54-rowloop.py`), where `dst - DX = 320` every time; sprite
dimensions from `tools/chains.py` over `arbre.io`; source attribution at `seg_0e97:0660`
over 198 and 182 rows in two windows (`tools/t55-source.py`).

### 4.15d Reading a frame: which sprite is on screen, and where

Because the blit is 1:1 (4.15c), a sprite on screen matches its stored bytes exactly. Probe
each sprite's longest **opaque run** against video memory, then verify the whole sprite.
`tools/onscreen.py` does this across all 98 assets. One frame, standing two cells south of
the starting NPC:

| asset | sprite | size | base | at | match |
|---|---|---|---|---|---|
| `plaine.io` | @24720 | 48x58 | 16 | (98, 68) | **100%** |
| `plaine.io` | @26120 | 48x67 | 16 | (146, 59) | **100%** |
| `plaine.io` | @24440 | 16x34 | 16 | (82, 93) | **100%** |
| `buste.io` | @6986 | 64x36 | 208 | (0, 147) | **100%** |
| `gerdep.io` | @11718 | 32x23 | 208 | (273, 101) | **100%** |
| `frise.io` | @50784 | 16x16 | 160 | (0, 0) | **100%** |
| `main.io` | @25760 | 16x16 | 160 | (0, 0) | **100%** |

So the outdoor scenery -- the bushes -- is `plaine.io` at **palette base 16**, and the
mouse cursor at (0,0) is a 16x16 sprite carried identically in `frise.io` and `main.io`.

**The NPC is not in any asset.** The same sweep, over every sprite of all 98 files at every
palette base, does not find the man standing in the middle of that frame -- while finding
seven other things in it at 100%. Nor is `bormin.io` on screen: 0 of its 12 sprites,
despite the name reading like a character. Tracked as T56.

Two plausible reasons, neither checked: his pixels may live in the ~38% of asset bytes no
sprite chain reaches (T51), or he is drawn through a path that transforms them.

**Evidence:** `tools/onscreen.py`, longest-opaque-run probe followed by whole-sprite
verification against `0xA0000`, opaque pixels only; the seven matches above are every hit
above 95% in that frame.

### 4.15e Three routines write a viewport pixel, and one of them draws the text

Hunting the drawing loops one at a time found the backdrop and then failed twice. Watching
**writes to one back-buffer pixel** settles it in a single run. The back buffer is at
`0xE0000` and the blit is 1:1, so screen `(x, y)` is `0xE0000 + y*320 + x`. Watching the
tree canopy at `(172, 65)`, against a control breakpoint on memory the program never
touches:

| site | live | control |
|---|---|---|
| `seg_0e97:06d5` `viewport_fill_rect` | 6 | **0** |
| `seg_0e97:0657` the opaque expander (loop at `0644`) | 6 | **0** |
| `seg_0e97:0597` the **masked** expander (loop at `0568`) | 3 | **0** |
| `seg_0000:3d64` `wait_loop` | 7 | 3514 |

The control run produced 7,709 stops across 171 sites in half the time, almost all of them
`wait_loop` -- which is exactly why it is needed. The three `seg_0e97` sites have **zero**
control hits, so they are real.

**So the viewport is drawn by three routines, not one:** a rectangle fill, an opaque
expander, and a masked expander. Earlier probes of the masked loop's row step caught only
panel content, which was the window, not the routine.

**And the masked loop draws the text.** Attributing its source at the row step
(`seg_0e97:059a`) while the panel caption reads FRAGONIR:

| sprite | size | drawn at |
|---|---|---|
| `main.io` @23272, @23662, @23740, @23896, @24286, @24598 | 16x9 each | x = 272, 286, 293, 300, 307, 314, at y=2 |
| `plaine.io` @32264 | 16x7 | x = 20, 44, 68 at y=81 |

Seven 16x9 sprites in a row at **7-pixel spacing** across the caption area: **`main.io`
carries the font**, one sprite per glyph. And `plaine.io` @32264 is a small scenery element
**tiled every 24 pixels** along y=81 -- the same tiling idea as the ground band.

**Evidence:** `tools/t56-writer.py` (MEMORY_WRITE on one back-buffer pixel, with a control
on never-written memory), and `tools/t54b-objects.py` at `seg_0e97:059a` grouping rows into
objects by `BP` and attributing `DS:SI`.

### 4.15f The NPC is `bormin.io`, and the sprite changes with distance -- but not predictably

**The starting NPC's sprite is `bormin.io`.** Capturing whole viewport frames -- send one
key, then collect row-step stops until none has arrived for 2.5s, so a frame is whole or it
is nothing -- and attributing `DS:SI` catches him being drawn:

| party cell | distance to the NPC | sprite | size | drawn at |
|---|---|---|---|---|
| (12,28) | ~3 | `bormin.io` @2152 | 16x29 | (224, 72) |
| (12,29) | ~3 | `bormin.io` @2152 | 16x29 | (136, 72) |
| (13,30) | ~2 | `bormin.io` @1424 | 32x45 | (12, 65) |
| (14,29) | 1 | `bormin.io` @3714 | **48x31** | (103, 60) -- **100%** vs VRAM, 779 px |

So the sprite drawn **does** change with distance, on the same object, which is the size
ladder in use on a character rather than on scenery.

**And the prediction failed.** `bormin.io`'s twelve sprites sort by height 7, 12, 15, 19,
29, 31, 35, 39, 45, 68 -- so from 16x29 at distance 3 and 32x45 at distance 2, the next rung
up at distance 1 should have been @5466, **32x68**. It is @3714, **48x31**: wider and
*shorter*. Verified against video memory, so it is not a mis-capture.

**The ladder is therefore not a monotonic size sequence.** Two readings, neither checked:
the sprites may be *parts* of a figure rather than whole ones at each range -- 48x31 at
(103,60) covers the upper body of a figure that is visibly ~60 px tall on screen, so
something else draws the rest -- or they may be poses, and which one is chosen depends on
more than range.

**What this settles and what it does not.** T56 is answered: the NPC's pixels are in
`bormin.io`, three offsets seen, one verified pixel-for-pixel. T54b is not: a prediction
made from two distances did not hold at a third, which is the acceptance criterion, so
"distance selects a rung" stays a description rather than a rule.

Two earlier claims this corrects. `bormin.io` was recorded as **not on screen, 0 of 12
sprites** (4.15d) -- true of that frame, where the party stood elsewhere, and wrong as a
statement about the asset. And `arbre.io` @18890 (48x38) was caught in the same session,
alongside @25490 and @25714, so its ladder is in use too.

**Evidence:** `tools/t54b-frames.py` (quiescence-based whole-frame capture at
`viewport_row_step_masked`, attributing `DS:SI` against every decoded asset); the distance-1
sprite independently confirmed by `tools/onscreen.py` at 100% of 779 opaque pixels;
`captures/t54b-adjacent.png` showing the figure at that distance.

### 4.15g A character is drawn from stacked parts, not one sprite per distance

The question T54b was asking -- which rung of a size ladder goes with which distance -- is
the wrong one for characters. Standing adjacent to the starting NPC, **two** `bormin.io`
sprites are on screen, stacked:

| sprite | size | at | match |
|---|---|---|---|
| `bormin.io` @3714 | 48x31 | (103, 60) | **100%** -- 779 of 779 opaque pixels |
| `bormin.io` @2770 | 48x39 | (104, 91) | **92.8%** -- 950 of 1024 |

They are contiguous: y 60..91 and y 91..130, one pixel apart in x. Together 48 x 70, which
is the figure as it appears on screen. The lower half's 74 wrong pixels are where grass and
flowers are drawn over his feet.

**So `bormin.io`'s twelve sprites are body parts at several ranges, not twelve whole
figures.** That explains the prediction that failed in 4.15f: 48x31 is not "a shorter rung
than 32x45", it is the *upper half* of a nearer figure. Sorting the sprites by height was
sorting a mixture of halves and wholes.

**What a rewrite needs instead of a ladder:** for each range, the set of parts and their
relative offsets. `@3714` over `@2770` at `dx = +1, dy = +31` is the adjacent pose; the
16x29 seen at three cells (4.15f) is presumably whole at that size, since nothing stacked
under it.

**Why the earlier sweep missed it.** `tools/onscreen.py` steps its search by one pixel but
the quick probe written to look for a second part stepped by two, and @2770's origin has an
odd y. A grid that skips the answer reports its absence -- the same shape as the scar about
zero-hit results being claims about the instrument.

**Evidence:** exhaustive single-pixel search over x 80..180, y 40..140 for both sprites
against live VRAM with the party adjacent and the dialogue panel dismissed
(`captures/t54b-nodialogue.png`); opaque pixels only, counts above.

### 4.15h Screen position: one solid number, and why the rest is hard

**88 pixels per lateral cell at three cells' distance.** The same NPC sprite, `bormin.io`
@2152 (16x29), was caught drawn at screen x **224** with the party at `(12,28)` and at
**136** with the party at `(12,29)` -- one cell east, 88 pixels left, same y (72), same
sprite.

That difference is the useful form. **Absolute position cannot be read from one frame**,
because a sprite's origin is not the object's centre: two lateral-zero observations of the
same NPC put its centre at 144 and at 127, so each sprite carries an anchor offset nobody
has measured. A difference between two frames cancels the anchor; a single frame does not.

**A second, weaker point.** Taking the NPC's cell as `(15,29)`, @1424 at `(13,30)` gives
about 116 pixels per cell at two cells' distance. A pure 1/z projection would predict 132
from the 88 at three cells. Same direction, wrong size -- but the NPC's cell is an
assumption and the sprite anchors differ, so this is a hint, not a measurement.

**Three things make the NPC the wrong object for this.** He appears to **move** -- `(13,29)`
became blocked between two visits; he is **occluded** at distance, so the framebuffer route
finds nothing from three cells away while the breakpoint sees him drawn; and his **map cell
is unknown**, which the acceptance criterion needs.

So T54c wants a fixed object whose cell can be established -- a tree that blocks a move,
which identifies its cell exactly -- measured by the breakpoint route at several lateral
offsets per distance.

**A second slope, from a fixed object.** A tree -- `arbre.io` @24842, 32x40 -- was caught at
screen x **153** with the party at `(13,43)` and at **191** at `(13,42)`: one cell west, 38
pixels east, **same sprite and same y (51)**, which is what makes it trustworthy.

| object | distance | pixels per lateral cell |
|---|---|---|
| the NPC, `@2152` at y=72 | 3 cells | **88** |
| a tree, `@24842` at y=51 | unknown, farther | **38** |

**And the two are consistent with an inverse law.** 88 at three cells implies a constant of
264, which puts the tree at 264/38 = **6.9 cells** -- and the tree *is* farther away, and
higher on screen (y=51 against 72), both of which agree. Suggestive, not established: the
tree's distance was derived from the slope, so using it to confirm the law would be
circular.

**The blocker is object identity, not measurement.** Testing the law needs the *same* object
at a second distance, and one row closer the same tree is drawn from different sprites
(`@25490` 16x27, `@25714` 16x15, `@23962` 16x65) while several trees are in view -- so
nothing says which sprite belongs to which tree. The NPC failed for a different reason
(4.15i: he walks), and the tree fails for this one.

**The instance list does not fix it, and that is a correction.** The plan was to read each
drawable's own viewport X/Y from its instance (FORMATS 3.17), giving objects an identity
that persists across frames. The instances do not hold those numbers.

Searching **all 640 KB** of conventional memory for the three origins drawn in one frame --
`(151,61)`, `(167,66)`, `(149,30)` -- as word pairs, in either order, gives **zero hits**.
A control in the same dump finds `(255,125)` four times, one of them at pool offset 138
exactly where the record sits, so the search works.

**So a viewport object's screen position is computed per frame and never stored.** It exists
only in `DI` at the row step. FORMATS 3.17 inferred that "instances carry viewport object
positions" from the *range* of X/Y values found in a pool scan -- 9..272 by 6..94, which is
the viewport rectangle -- rather than from matching any drawn position. Values falling in a
plausible range is not evidence about what a field holds; that is the same mistake as the
palette group read out of word 0 (3.10).

**What the pool actually contains**, scanned for the `0x7fff` bounding-box sentinel: exactly
**two** records, at offsets 116 and 154, carrying `(255,125)` and `(319,199)`. Those are
`main.io`'s two rectangle declarations and nothing else -- consistent with the entity block
being zero beyond +128 (3.17), and with there being no per-object drawable record for the
viewport at all.

**Identity by draw order does not work either, and that is the fourth approach.** The idea
was that the nth object of a frame is the nth object, so ordinal position gives identity
without needing to recognise the sprite. It requires the draw sequence to be reproducible,
which it is not: two frames taken at the same cell after the same key gave **11 and 13
objects with none identical in the same position**, and widening the quiescence window from
2.5s to 6s changed the counts but not the conclusion.

The cause is the instrument, not the game. A breakpoint at the row step slows the machine so
far that a redraw interleaves with everything else, so "one key press" does not map onto
"one frame" -- some presses are refused and redraw nothing, some produce several bursts.

**So object identity is not available**, by sprite (two trees share one), by tracking (the
NPC walks, trees are indistinguishable), by the instance list (the numbers are not stored)
or by draw order (not reproducible). Four approaches, four different reasons.

**What a rewrite should do instead.** Take the projection as `pixels per lateral cell =
264 / distance` from the two measured slopes, and calibrate the per-sprite anchor by eye
against a screenshot. That is enough to place objects; it is not a derivation, and it is
recorded as such.

**Evidence:** the two @2152 sightings from `tools/t54b-frames.py` at `(12,28)` and
`(12,29)`, and the two @24842 sightings at `(13,43)` and `(13,42)`; the anchor discrepancy
from the four sightings tabulated in 4.15f; three failed attempts at more lateral points
with `tools/t54c-slope.py`, which found nothing because the framebuffer cannot see an
occluded distant sprite.

### 4.15i NPCs walk around, and an occupant blocks a cell

**The starting NPC moves.** Cell `(13,29)` was refused, then walked onto, then refused
again, within a few minutes and with no change to the map:

```
cont1.fic[(13,29)] = 0x02        the same value throughout
(12,29) -> (13,29)  refused      he was standing there
(12,29) -> (13,29)  MOVED        he had moved on
(14,29) -> (15,29)  refused      he was there now
(14,29) -> (13,29)  refused      he had gone back behind the party
```

**So occupancy blocks movement, and the cell value does not.** That settles the anomaly
behind 6.7b's "blocking is not a function of the cell value": `0x0A` refused a move in one
place and allowed it in another because something was *standing* on one of them. A rewrite
needs an occupancy layer over the grid, separate from terrain.

**And it makes the NPC useless as a measurement target.** Three tasks have now failed on it
-- T54c's lateral slope, T54d's part sets, and an attempted distance-4 prediction -- because
the distance to him changes while the measurement is being taken.

**The part sets, as far as they got.** With him pinned at `(15,29)` and the party directly
south, so lateral offset zero:

| distance | parts | origins |
|---|---|---|
| 1 cell | `@3714` 48x31 **and** `@2770` 48x39 | (103,60), (104,91) |
| 2 cells | `@1424` 32x45 | (144,65) |
| 3 cells | `@2152` 16x29 | (136,72) |

So the number of parts changes with range: two when adjacent, one beyond that. The
distance-4 prediction -- the next smaller 16-wide sprite, `@2392` 16x19 -- could not be
tested, because he walked behind the party before the party could retreat.

**Evidence:** the four move attempts above, each read from the position bytes rather than
from the screen; `tools/t54b-frames.py` captures at the three distances; `@3714` confirmed
at 100% of 779 opaque pixels by `tools/onscreen.py` at distance 1.

### 4.18 Why screen positions are hard to find, and what is ruled out (T40)

Three approaches to deriving the portrait's origin (0, 147) rather than measuring it, all
negative, and the negatives narrow it usefully.

**Positions are not stored as precomputed offsets.** `147 * 320 = 47040` -- what a linear
destination for the portrait row would be -- appears nowhere in `start-unpacked.exe` and
only twice across all 98 decoded assets, both inside image data (`krog.io` 22508,
`preson.io` 2051). So the destination is computed at draw time from an x and a y, not
looked up.

**CORRECTED (T40b): it draws the UI, just not the viewport.** The paragraph below was
too broad, and it was built on a bug in my own tool -- `tools/t29c-action.py` keyed
function call counts on the **offset alone**, discarding the segment. Five segments are
present (`0x17d`, `0xabe`, `0x1014` = `seg_0e97`, `0x1554`, `0xf000`), so addresses were
mislabelled: everything reported as `seg_0000:038b`, `:0008` and `:01a8` in FINDINGS 4.16
is really in **`seg_0e97`**. Both diff tools now key on (segment, offset).

Re-measured with that fixed: **`seg_0e97:038b` fires 120 times on a portrait click against
0 idle**, and 106 on an ACTION menu draw. So the in-game sprite blitter *is* in that
family, and is now `sprite_blit_ingame` in `ishar.chani`. What it does not draw is the
**3D viewport** -- T11p's zero-in-30s-of-walking stands, and the viewport has its own
routines (FORMATS 3.13d). The two results were never in conflict.

Still true from the probes below: `sprite_mode_dispatch` (`seg_0e97:0a30`) and the
mode-`0x10` path take 0 hits in the same windows, so the in-game path reaches the blitter
**without going through the mode dispatcher** -- there are two ways into this sprite code.

**Superseded reasoning follows.**

**The sprite family documented in FORMATS 3.13c is not what draws the game.**
`sprite_mode_dispatch` (`seg_0e97:0a30`) and its mode-`0x10` path (`seg_0e97:0b4c`) took
**0 hits** while the ACTION menu was opened and closed, against **44** for a control at
`vm_run` in the same session. That is consistent with T11p, which found `seg_0e97:038b`
firing 445 times during launcher/title/intro and **zero in 30 seconds of walking**.

The distinction matters and is easy to misread: the *format* in 3.13c is right -- `buste.io`'s
portrait decodes byte-for-byte against VRAM as a mode `0x10` sprite (3.13b) -- but the
*code* described there is the launcher and intro renderer. **The in-game blitter has not
been identified**, and finding it is a prerequisite for this task rather than part of it.

**Breakpoint probing of draw routines defeats itself.** Each attempt produced 5,000-6,000
stops in 20 seconds, which slows the machine so much that the click being probed never
gets processed -- the same trap as T37c, where a `vm_run` breakpoint froze the screen for
270s. Any further work here needs the call-count diff (`tools/t29c-action.py`), which does
not stop the machine, to identify the routine first, and a breakpoint only once the
address is known.

**Evidence:** the constant search across the executable and all 98 assets; three probe runs
with a live control; T11p's earlier hit counts.

### 4.19 Every asset, what it is, and whether a rewrite can use it

The distinction that matters for a port is **not** how well a file is understood -- it is
whether it holds *data you load* or *logic you reimplement*. `affobj.io` is well understood
and **unusable**: it contains no data at all, only bytecode that toggles entity flags.

| category | files | for a rewrite |
|---|---|---|
| **art** | 55 | **load directly** -- decoded byte-exactly, two verified against live VRAM |
| **art + script** | 8 | art loads; the script half is logic |
| **text** | 8 | **load directly** -- `message*` and `textin*`, four languages each |
| **name tables** | 4 | **load directly** -- `sos*`, filenames the game resolves |
| **script only** | 8 | **reimplement** -- no data in them |
| **unclassified** | 15 | unknown |

So **67 of 98 assets are usable today** (art, text, name tables), 16 carry logic, and 15 are
still unidentified.

The `.fic` files sit outside this: `cont1..6.fic` are **exactly 90x54** world grids (4,860
bytes each) and load directly; `en1.fic` and `tab1.fic` are unexplained.

| file | bytes | kind | what it is | for a remake |
|---|---|---|---|---|
| `affobj.io` | 1,432 | script | object-display logic — toggles entity visible flags (8.0) | reimplement — logic, no data |
| `arbre.io` | 25,976 | art + script |  | **art usable** (15 sprites); logic to reimplement |
| `auteur.io` | 65,984 | full page | the credits card, a whole 320x200 VGA page (3.18) | **use directly** — one page |
| `azal.io` | 18,368 | art |  | **use directly** — 5 sprites |
| `barbare.io` | 17,792 | art |  | **use directly** — 27 sprites |
| `blancpc.io` | 2,094 | unknown | blank/clear frame, the only stored-mode asset (3.11) | not classified |
| `bormin.io` | 7,296 | art |  | **use directly** — 7 sprites |
| `buste.io` | 46,064 | art | character portraits (3.13b, verified vs VRAM) | **use directly** — 33 sprites |
| `colcave.io` | 28,200 | art |  | **use directly** — 14 sprites |
| `darkm.io` | 10,544 | art |  | **use directly** — 18 sprites |
| `darkwiz.io` | 9,240 | art |  | **use directly** — 9 sprites |
| `dead.io` | 65,984 | full page | **the demon frame** shown when the party is wiped — verified vs VRAM (3.18) | **use directly** — one page |
| `dealer.io` | 12,352 | art |  | **use directly** — 19 sprites |
| `dplt.io` | 3,376 | script |  | reimplement — logic, no data |
| `dragon.io` | 16,296 | art |  | **use directly** — 13 sprites |
| `dwarrior.io` | 13,448 | art |  | **use directly** — 16 sprites |
| `en1.io` | 5,496 | art |  | **use directly** — 7 sprites |
| `encont.io` | 2,008 | script |  | reimplement — logic, no data |
| `fbuis.io` | 12,864 | art |  | **use directly** — 8 sprites |
| `fcave.io` | 5,216 | unknown |  | not classified |
| `fcave2.io` | 15,344 | unknown |  | not classified |
| `fond.io` | 12,928 | art + script |  | **art usable** (5 sprites); logic to reimplement |
| `fontaine.io` | 6,128 | art |  | **use directly** — 10 sprites |
| `foret.io` | 57,728 | art |  | **use directly** — 33 sprites |
| `fragorn.io` | 7,576 | art |  | **use directly** — 9 sprites |
| `frise.io` | 53,808 | art + script | UI chrome — right panel, action bar, life bars (4.15) | **art usable** (14 sprites); logic to reimplement |
| `ftemple.io` | 17,056 | art |  | **use directly** — 3 sprites |
| `fville.io` | 4,800 | art |  | **use directly** — 2 sprites |
| `gaz.io` | 3,192 | unknown |  | not classified |
| `geant.io` | 16,856 | art |  | **use directly** — 22 sprites |
| `gerdep.io` | 14,472 | script |  | reimplement — logic, no data |
| `geren.io` | 13,088 | script | palette bank — 16 sub-palettes of 16 (3.9) | reimplement — logic, no data |
| `goul.io` | 9,688 | art |  | **use directly** — 8 sprites |
| `iboishar.io` | 132,728 | unknown | the largest asset in the game; layout unread (3.19, T47) | not classified |
| `incave.io` | 15,752 | art |  | **use directly** — 12 sprites |
| `intmais.io` | 79,656 | art | house interiors | **use directly** — 31 sprites (89% of the file) |
| `inville.io` | 6,576 | art |  | **use directly** — 6 sprites |
| `itaverne.io` | 44,160 | art |  | **use directly** — 9 sprites |
| `kiriela.io` | 7,296 | art + script |  | **art usable** (9 sprites); logic to reimplement |
| `knight.io` | 17,456 | art |  | **use directly** — 16 sprites |
| `krog.io` | 32,584 | art |  | **use directly** — 18 sprites |
| `lacustre.io` | 24,088 | art + script |  | **art usable** (22 sprites); logic to reimplement |
| `logo.io` | 40,632 | art | Silmarils publisher logo (verified vs VRAM) | **use directly** — 4 sprites |
| `loup.io` | 17,040 | art |  | **use directly** — 16 sprites |
| `main.io` | 26,384 | art + script | the setup program — loads every asset (7) | **art usable** (1 sprites); logic to reimplement |
| `map.io` | 21,368 | unknown |  | not classified |
| `marchand.io` | 40,888 | art |  | **use directly** — 2 sprites |
| `mcave.io` | 86,544 | art | cave | **use directly** — 45 sprites |
| `medus.io` | 15,536 | art |  | **use directly** — 13 sprites |
| `message.io` | 8,712 | text |  | **use directly** — strings (10) |
| `messaged.io` | 8,600 | text |  | **use directly** — strings (10) |
| `messagee.io` | 8,416 | text |  | **use directly** — strings (10) |
| `messagei.io` | 8,600 | text |  | **use directly** — strings (10) |
| `minotor.io` | 20,864 | art |  | **use directly** — 32 sprites |
| `momo.io` | 23,128 | art |  | **use directly** — 11 sprites |
| `monstre.io` | 2,016 | unknown |  | not classified |
| `morgu.io` | 7,520 | art |  | **use directly** — 8 sprites |
| `naim.io` | 16,344 | art |  | **use directly** — 20 sprites |
| `objet.io` | 35,536 | art |  | **use directly** — 15 sprites |
| `objint.io` | 4,720 | art |  | **use directly** — 6 sprites |
| `orc.io` | 15,328 | art |  | **use directly** — 18 sprites |
| `pabo.io` | 9,752 | art |  | **use directly** — 7 sprites |
| `param.io` | 15,680 | script |  | reimplement — logic, no data |
| `pcave.io` | 5,384 | art |  | **use directly** — 4 sprites |
| `plaine.io` | 32,488 | art + script |  | **art usable** (23 sprites); logic to reimplement |
| `predator.io` | 14,352 | art |  | **use directly** — 9 sprites |
| `presen.io` | 143,608 | art | Ishar title card | **use directly** — 7 sprites |
| `preson.io` | 51,424 | unknown |  | not classified |
| `presti.io` | 22,184 | art | title lettering, 4bpp dithered (3.14) | **use directly** — 9 sprites |
| `rampart.io` | 28,008 | art |  | **use directly** — 24 sprites |
| `rplaine.io` | 30,048 | art + script |  | **art usable** (17 sprites); logic to reimplement |
| `samb.io` | 32,880 | script |  | reimplement — logic, no data |
| `saub.io` | 46,024 | unknown |  | not classified |
| `scave.io` | 26,664 | unknown |  | not classified |
| `scomb.io` | 10,472 | unknown |  | not classified |
| `skelet.io` | 8,424 | art |  | **use directly** — 11 sprites |
| `sorcier.io` | 9,024 | art |  | **use directly** — 13 sprites |
| `sos.io` | 4,064 | name table |  | **use directly** — filenames (10.1) |
| `sosd.io` | 3,976 | name table |  | **use directly** — filenames (10.1) |
| `sose.io` | 3,888 | name table |  | **use directly** — filenames (10.1) |
| `sosi.io` | 3,976 | name table |  | **use directly** — filenames (10.1) |
| `souris.io` | 3,856 | script | mouse cursor sprite | reimplement — logic, no data |
| `spectre.io` | 9,968 | art |  | **use directly** — 10 sprites |
| `spider.io` | 4,712 | art |  | **use directly** — 4 sprites |
| `stage.io` | 72,968 | art |  | **use directly** — 2 sprites |
| `stel.io` | 7,128 | art |  | **use directly** — 11 sprites |
| `telep.io` | 2,016 | unknown |  | not classified |
| `temple.io` | 49,872 | art |  | **use directly** — 14 sprites |
| `textin.io` | 11,896 | text |  | **use directly** — strings (10) |
| `textind.io` | 11,568 | text |  | **use directly** — strings (10) |
| `textine.io` | 11,480 | text |  | **use directly** — strings (10) |
| `textini.io` | 11,472 | text |  | **use directly** — strings (10) |
| `theend.io` | 142,888 | unknown | layout unread, and the only asset with no palette record (3.19, T47) | not classified |
| `village.io` | 24,584 | art |  | **use directly** — 21 sprites |
| `ville.io` | 100,712 | art | town | **use directly** — 55 sprites |
| `wardog.io` | 10,384 | art |  | **use directly** — 12 sprites |
| `wiz1.io` | 9,816 | art |  | **use directly** — 13 sprites |
| `zombi.io` | 11,272 | art |  | **use directly** — 21 sprites |

**Two honest caveats.** "Art" means a sprite chain was found and rendered, and only
`logo.io` (8bpp), `buste.io` (4bpp) and `dead.io` (a whole page) have been compared
pixel-for-pixel against the running game -- the other 53 are decoded by the same verified
code path but not individually checked. And "unclassified" is not "empty": `monstre.io` and
`telep.io` are known to be script (3.16) but have no entry set yet, so nothing in them can
be read.

**Nine sizes in this table changed** when the header's size field turned out to be 24 bits
rather than 16 (FORMATS 3.0). The old figures were what a truncated `u16` produced, and they
are what made `dead.io` look "too small for the demon frame" and `intmais.io` look like a
33 KB file with two sprites in it. The corrected reading adds ~470 KB of decoded content and
124 sprites.

**Evidence:** sprite counts from the re-extracted `captures/assets/`; entry sets from
`.ish/t37f-entries.json`; text and name-table identification from section 10; the nine
corrected sizes from FORMATS 3.0, one of them (`dead.io`) checked byte-for-byte against
live VRAM.

### 6.10 The scripts can compute: the VM has a full operator set (T46)

The encoding is in FORMATS 6.1b; what it means for the game belongs here. Ishar's scripts
are not a list of canned commands. The expression table holds **fifteen operators in a
row**, `0x42`..`0x5e`:

`&` `|` `^` `^~` `==` `!=` `<=` `>=` `<` `>` `+` `-` `/` `%` `*`

-- the three bitwise ops, all six comparisons, and five arithmetic ones including **integer
division and remainder**. Operands are nested expressions, so they compose to arbitrary
depth.

That is a general-purpose expression language, and it reframes what the remaining unknowns
look like. Combat damage, spell cost, a quest condition -- none needs a hidden table in the
executable if a script can compute it inline. So the expectation for T21/T22/T23 should be
that the rules live in **bytecode arithmetic**, not in data still to be found, and reading
them is now possible: `tools/vmi.py --listing` renders expressions infix.

**Evidence:** each operator classified by the arithmetic instruction it applies, the six
comparisons by their conditional jump (`jz`, `jnz`, `jle`, `jge`, `jl`, `jg`, in opcode
order); FORMATS 6.1b carries the full 112-row table.

### 4.19e A map cell reaches a decision: read, store, switch

The path from the world map to a decision is now readable end to end, offline, in
`lacustre.io`'s bytecode.

**1. Read.** At offset 1190:

```
1e                     evaluate, then store
  38                     begin an expression sequence
    12 18                  frame var 24        -- a subscript
    40                     push
    12 19                  frame var 25        -- the other subscript
    26 80 00               global[0x0080 + index]   -- THE MAP CELL
  3a                     end the sequence
12 21                  store byte -> frame var 33
```

**Statement `0x1e` is evaluate-then-store**, which nothing had recorded: after the
expression it does `lodsb / mov di,ax / jmp cs:[di+029ch]`, dispatching the next byte
through the store table. Store `0x12` (`vm_store_byte_var`, `seg_0000:71c1`) is
`mov es:[bp+di], dl`. So the cell value lands in **frame variable 33**.

**2. Switch.** At offset 1410, statement `0x2f` (FORMATS 7.2g):

```
2f  12 21  03  ca ff  0a 00  32 00  30 00  58 00
^   ^      ^   ^      ^------ four signed displacements
|   |      |   bias = -54
|   |      case count 3, so cases 0..3
|   frame var 33 -- the cell value
switch
```

Selector is `cell - 54`, valid 0..3, so it dispatches on **cell values 0x36..0x39**:

| cell | goes to |
|---|---|
| `0x36` | 1428 |
| `0x37` | 1470 |
| `0x38` | 1470 -- shares an arm with 0x37 |
| `0x39` | 1512 |

Those four values are exactly the run in `cont1.fic` at column 17, rows 25-33:
`0x38, 0x36, 0x37, 0x36, 0x39, 0x36, 0x39, 0x36, 0x39` -- a vertical structure whose cells
this switch is written to handle.

**3. The arm tests the party's facing.** Case `0x36` at 1428 opens
`1f 38 1e 7e 13 4a 00 02 ...` -- load global `0x137E`, compare with 2.

**`+0x137E` is the byte immediately after the party's row and column** (`+0x137C`,
`+0x137D`), so the party's record is at least three fields. Read live it is **2**, and
ACTION -> ORIENTATION reports **"E : OSGHIROD"** at the same moment -- so 2 is East, on one
observation. That is the first handle anyone has had on the facing the arrow keys do not
change (6.7b).

**What this settles.** A cell value is data; what it *means* is a switch arm in the scene
script, and arms are shared (`0x37` and `0x38` go to the same place). So there is no
cell-to-sprite table to extract, and a rewrite either ports these switches or reimplements
the behaviour. It also shows the shape to look for in every scene asset: `26 80 00`
followed within a few statements by `2f` on the variable it was stored in.

**Not established:** the path from the arm to a *draw*. The arms were not followed past
their first branch.

**Evidence:** the bytes above, decoded against the statement, expression and store tables
`tools/vmi.py` reads out of the image; `seg_0000:291b` and `seg_0000:71c1` read from the
emulator's disassembler; `+0x137E` read live at `es:[ss:[0bf6] + 0x137e]` with the
ORIENTATION dialogue on screen (`captures/t11g3d-orient.png`).

### 4.20 The death screen is a file, and eight other assets were being truncated

Chasing which script draws the demon frame ended somewhere else entirely: **no script
draws it.** `dead.io` *is* the picture — a 320x200 page of palette indices copied to
`0xA0000` behind a short script and its palette (FORMATS 3.18).

It did not look that way because the decoder was reading a 24-bit size field as 16 bits
(FORMATS 3.0), so `dead.io` decoded as the first 448 bytes of a 65,984-byte asset. The
same truncation hit **nine assets** — every one over 64 KB:

| what changed | before | after |
|---|---|---|
| decoded content across the corpus | — | **+470 KB** |
| `mcave.io` sprites | 4 | 45 |
| `intmais.io` sprites | 2 | 31 (89% of the file accounted for) |
| `ville.io` sprites | 33 | 55 |
| `presen.io` sprites | 4 | 7 |
| assets whose declared size >= their file size | 93 / 106 | **106 / 106** |

The evidence that something was wrong had been sitting in FORMATS 3.0 since it was
written: thirteen assets declared a decompressed size *smaller than their own compressed
file*. That was recorded as a curiosity and rounded off.

**Two things this settles.** The party-wipe screen (4.17) needs no `dead.io` entry set to
reproduce — it is one page and one palette, ready to use. And "`dead.io` is 448 bytes, too
small for the demon frame" (FORMATS 3.16) was a correct argument from a broken premise: the
reasoning was fine, the number came from our own bug.

**What it does not settle.** `theend.io` (142,888) and `iboishar.io` (132,728) are still
unreadable — no sprite chain, no page that renders, and `theend.io` has no palette record
at all. 275 KB, the largest unexplained region in the corpus (T47).

**Evidence:** `dead.io`'s 64,000 bytes compared against the emulator's framebuffer at
`0xA0000` with the demon frame on screen -- **64,000 / 64,000 identical**; the 24-bit width
confirmed independently by the chunked decoder at `seg_0000:79a5` (`asset_decode_chunked`)
and by running the LZ bit stream to exhaustion on all 97 LZ assets, where the `u24` size
predicts the end for 97 and the `u16` for 88.

## 5. Known defects (ours and the game's)

### 5.0 A second garbage-execution fault

A traced boot died with `Instruction requires a memory operand but encoding selects a
register (modrm mod=3)` — a decode failure, so execution had again left real code. Same
family as §5.1 but a different symptom, and it happened while keys were being sent from
a second process during a GDB trace. Not yet characterised; noted so it is not mistaken
for §5.1 when it recurs.

Seen again on 2026-09-09, same text, at `CS:IP=017D:194D`, `Cycles=712803714`, during
a T08 trace that was driving keys through the language menu and intro.

**It is not "the intro crashes".** Ordinary play reaches gameplay: the user produced a
screenshot of the party standing outside the tree in Fragonir in a normal `run.sh`
session. So the fault is specific to some runs -- the traced/key-driven ones so far --
and any claim of the form "the game dies during the intro" is unsupported.

Two failures around this are worth keeping, because both were expensive:

- The frozen frame during the trace was reported to the user as "the intro is minutes
  long". It was this fault, already in the log. See the still-screen scar in
  `CLAUDE.md`.
- The run was left going for roughly twenty minutes after the machine was already dead,
  because nothing was watching. `tools/gdbtrace.py` now polls the log every 2s and
  aborts with `EMULATOR FAULTED`.

**Evidence:** `.ish/spice86.log` from the T08 attempts; the tracer's socket was reset
when the emulator exited. Contrast case: user screenshot of live gameplay from
`run.sh`.

### 5.3 The intro crash is intermittent, and it is not the FPU

Four faults, then a fifth, all inside one ~100-byte window of `seg_0e97`, and in
every one the opcode Spice86 names is **not** the byte at the CS:IP it names:

| reported | byte actually there |
|---|---|
| `1014:0EC6` | inside the 5-byte `call [0e97:0ec9]` at `0ec3` |
| `1014:0ECD` | `57` = `push di` |
| `1014:0F08` | `0f`, the displacement of the `jmp short` at `0f07` |
| `1014:0F0A` | `26`, an ES: prefix mid-instruction |
| `1014:0F2A` | same window |

`seg_0e97:0ec9` is an ISR prologue -- `push ax/bx/cx/dx/di/si/ds/es/bp`. So each
fault is execution entering that handler **at the wrong offset**, landing mid
instruction. That is a stale/garbage entry, the 5.1 family -- not an unimplemented
x87 escape. It supersedes 5.2's guess that 5.0 is FPU-related: 5.2's own `0xDA at
1014:0F0A` sits in this window, and `0f0a` holds `26`, not `da`.

**It is intermittent.** Same drive, same budget:

| run | audio | outcome |
|---|---|---|
| 1 | on | faulted 46.2s |
| 2 | `--audio none` | clean 210s, intro rendered (`captures/t08-audionone.png`) |
| 3 | `--audio none` | faulted 45.1s, `0xDA at 1014:0F2A` |

Run 2 was written up here as "the crash is the sound driver" on the strength of
runs 1 and 2 alone. Run 3 disproved it within minutes. One A and one B is not an
A/B -- the scar for this was already in `CLAUDE.md` ("A plausible cause is not a
cause") and got walked past anyway.

So: the fault is **not** caused by audio, fires at ~45s regardless, and a run that
survives it is luck. Traces must be retried, and a tracer must abort on the fault
rather than burn its budget -- which is what `tools/gdbtrace.py` now does.

**Evidence:** the three runs above; bytes read from `start-unpacked.exe` at each
reported address.

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

### 6.4 Attributing opcodes to actions, and why input is the blocker (T29c)

**CORRECTED (T29c2): the game does use the mouse.** The paragraph below is right about
what it measured and wrong about what it concluded, and the reason is the "a trace taken
mid-game cannot see what startup did" scar. Traced from a **cold start**, the game makes
eight INT 33h calls during boot -- `AX=0x00` reset (x2), `0x0f` mickey/pixel ratio (x2),
`0x04` set position, `0x07` and `0x08` ranges, and finally **`AX=0x0c`, install event
handler, with the callback at `ES:DX = 017d:1249`** (`mouse_event_handler` in
`ishar.chani`). After that it never calls INT 33h again, so a mid-game window sees nothing.

**FIXED (T29c3).** One line each for `Mouse` and `MouseDriver` in Spice86's
`Spice86DependencyInjection.cs`: they subscribed to `_gui as IGuiMouseEvents` while the
keyboard subscribes to the `InputEventHub`. Injected mouse events go into the hub, nothing
was listening to the hub's mouse events, and in headless mode `_gui` is the `HeadlessGui`,
which by its own comment "never raises these events". Passing `inputEventHub` instead --
it wraps the GUI, so real pointer input is unaffected -- makes the whole chain work.

After the fix: the callback at `017d:1249` fires with `AX=1` on movement (0 hits before,
against a live control of 507), **the game's own cursor appears and tracks the pointer**,
and clicking `MAP` in the ACTION menu opened the world map of KENDORIA -- 65.4% of the
screen changed. `captures/t29c3-action-menu.png`, `captures/t29c3-map-clicked.png`.

So the mouse is now drivable from the harness, and T29c's whole premise -- that combat and
magic cannot be reached -- is dead.

**The blocker as it was (superseded):** With the callback address
known, driving the harness's mouse -- moves and clicks, and with the *correct* units, see
below -- produces **0 hits on the callback** and **0 hits on the BIOS INT 74h handler**,
against **507** for a control breakpoint at `vm_run` in the same session. So injected
mouse input never raises IRQ12, INT 74h never runs, and Spice86's mouse driver never
reaches the callback it has correctly registered. The machinery exists
(`MouseDriver.cs:129-157` invokes the user callback, and `BiosMouseInt74Handler` is
installed) -- the trigger does not arrive.

**`send_mouse_move` takes normalised 0.0-1.0 coordinates, not pixels.** `{"x":160,"y":100}`
answers `Mouse moved to (1.000, 1.000)` -- clamped to the corner, so the pointer never
moves and no event could fire. Both unit conventions were tried here and neither reaches
the callback, so this is not the cause, but any future mouse work has to use fractions.

**Evidence:** INT 33h entry breakpoint from a paused cold start, catching all eight calls
with `ip` checked against the armed address; callback and INT 74h probes with the same
check and a live control; Spice86 source at the paths named.

**Superseded reasoning follows.**

**The game does not use the BIOS mouse.** A breakpoint on the INT 33h handler records
**zero calls in 20 seconds** of the game running, and the mouse IRQ vectors are all still
the BIOS stub -- INT 0Bh (COM2), INT 0Ch (COM1) and INT 74h (PS/2) point at `f000:00xx`.
The only vectors the game hooks are **INT 09h** (keyboard, `017d:1072`) and **INT 08h**
(timer). So `send_mouse_move` / `send_mouse_button` reach nothing, and any UI that needs
pointer selection cannot be driven from the harness yet.

**F1 opens character 1's ACTION menu**, which is the party verb list:

```
GIVE ITEM     PICK LOCK
GIVE MONEY    ORIENTATION
KILL          FIRST AID
DISMISS       MAP
RECRUIT       EXIT
```

`captures/t29c-f1.png`. Menu *entries* could not be selected: arrow keys, Return, Escape
and first-letter keys (`f` for FIRST AID, `m` for MAP) all redraw the menu and change
nothing, so selection is presumably pointer-driven.

**One primitive attributed.** `vm_op_draw_menu` -- opcode `0x4b`, `seg_0000:3a84`, arity 1,
writes `ss:[0c0e]` -- runs 30 to 46 times whenever that menu is drawn and never in the idle
baseline, together with its engine helper `menu_draw_item` (`seg_0000:35cf`) at exactly one
call per entry. Confirmed across five separate triggers.

**Method that works, for whoever continues this.** `tools/t29c-action.py` snapshots
Spice86's per-function call counts, performs one action, snapshots again, and reports only
routines absent from an idle control run (`.ish/t29c-idle.json`). The control matters: the
language core runs 40,000-60,000 times either way and buries anything rarer. The technique
is sound -- it is the *actions* that are unreachable, not the measurement.

**Evidence:** INT 33h breakpoint (0 hits/20s); interrupt vector dump; five action diffs
with the idle baseline; screenshots `captures/t29c-before.png`, `t29c-f1.png`.

### 6.5 Ishar's mouse (T29d) — ~~and why the harness cannot use it~~

**The second half of this title was wrong and is struck out (T29c3).** The harness *can*
drive the mouse. Spice86's `Mouse` and `MouseDriver` subscribed to the GUI while the
keyboard subscribed to the `InputEventHub`, and in headless mode the GUI never raises mouse
events, so injected input was dropped before reaching the driver -- one line each to fix.
The game's callback at `017d:1249` now fires, its cursor tracks the pointer, and ACTION-menu
entries can be clicked. The description of the game's own mouse setup below is unaffected.

The game **does** use a mouse -- an earlier reading that it did not was drawn from a trace
taken after startup. Breaking on the INT 33h handler from boot catches the whole setup:

| call | meaning |
|---|---|
| `AX=0x00` | reset / detect (twice: at 0.1s and 4.1s) |
| `AX=0x0f` | set mickey-to-pixel ratio |
| `AX=0x04` | set cursor position to (160, 100) -- screen centre |
| `AX=0x07` | set horizontal range 0..319 |
| `AX=0x08` | set vertical range 0..199 |
| `AX=0x0c` | install event handler, mask `0x3f`, at `017d:1249` |

So the pointer is **event-driven, not polled** -- which is why a trace taken mid-game sees
zero INT 33h traffic and looks like a game with no mouse support.

`mouse_event_handler` (`seg_0000:1249`) does nothing but record its arguments:

```
mov cs:[11c1], bx      ; buttons
mov cs:[11bd], cx      ; x
mov cs:[11bf], dx      ; y
retf
```

and `mouse_read_state` (`seg_0000:1259`) reads them back, gated on `ss:[0ca3]` being zero.

**Spice86 does not deliver INT 33h function 0x0c callbacks.** A breakpoint on
`seg_0000:1249` records **zero hits** across a dozen `send_mouse_move` calls. That is an
emulator limitation, not a gap in the game's behaviour, and it is what makes every
pointer-driven part of Ishar -- the ACTION and ATTACK buttons, and therefore combat, magic
and inventory -- unreachable from the harness.

**The obvious workaround does not work either.** `tools/mouse.py` writes the three
variables directly, which should be exactly equivalent to the callback firing. Moving the
pointer changes no pixels, and a click on the ACTION button changes none: the screen is
byte-identical before and after. So `ss:[0ca3]`, or an event flag the handler's caller
sets, also gates the read.

**Evidence:** INT 33h trace from a cold boot (8 calls, all during startup); a breakpoint
on `seg_0000:1249` during `send_mouse_move` (0 hits); two screenshot comparisons at 0
pixels changed.

### 6.6 Evidence that the palette group is not word 0's high byte (T11r)

`buste.io` holds the party portraits. The sprite at 14802 (64x44) has
`word0 = 0x0010`, so under the model in FORMATS.md 3.10 its palette group is 0 and its
colours are entries 0..15 of the scene palette.

Rendered that way it is a **green face**. Rendered against each of the 16 groups in turn
(`captures/buste-all-groups.png`), several give a natural bearded face with plausible
skin, hair and cloth -- groups 4, 6, 8, 9 and 10 all look like a person, and group 0 does
not. Using `fond.io`'s verified palette instead of the bank changes nothing, because
`bank#0` and `fond.io`'s palette are byte-identical.

So either the group is not the high byte of word 0, or portraits are drawn against a
palette that has not been identified. The model was only ever inferred -- the low byte is
constant at 16 and the high byte spans 0..15, which is suggestive and not a measurement
(T11r) -- and this is the first evidence that actively contradicts it.

The on-screen portrait for comparison is `captures/portrait-onscreen.png`, cropped from
the live game: pale skin, a magenta circular background and silver armour. It is a
different character from the sprite at 14802, so it is not a pixel comparison, but it
does say what a correct portrait looks like.

**Evidence:** `captures/buste-all-groups.png` (the same 64x44 sprite under all 16 groups)
and `captures/buste-bank0-vs-fond.png`.

### 6.7 The map grid's values: two populations (T11g3, partial)

`cont*.fic` is a 90x54 grid of one byte per cell (FORMATS.md 3.12), and the editor
prompts left in `main.io` name what the world is made of -- *contrée, région, zone,
tableau* (7.2). Counting connected components of each value separates the byte values
into two clear populations:

| value | cells (cont1) | components | shape | reading |
|---|---|---|---|---|
| `0x00` | 2131 | 252 | large blobs | open / empty ground |
| `0xCD`, `0xCC` | 524, 255 | 9, 6 | large blobs | outside the playable area (MSC uninitialised fill) |
| `0xCE` | 232 | 5 | one-cell-wide curves | **the boundary outline** -- mean 1.96-1.99 orthogonal same-value neighbours in all six files |
| `0x9D`, `0xE1`, `0xE5`, `0xE6` | 130-970 | few | large blobs | area/terrain classes |
| `0x02`-`0x18` | 58-181 each | ~1 per cell | scattered singletons | per-cell markers -- objects, entrances or encounters |

The split is the finding: **high byte values form a small number of large regions, low
values are isolated single cells.** A base terrain painted in areas with sparse
individually-placed markers on top is what that looks like.

**Ruled out: a cell is not two interleaved bytes.** Splitting each file into even and odd
byte planes gives two planes with statistically identical profiles (52 vs 54 distinct
values, 30% vs 30% above 100) that both autocorrelate at lag 45 -- which is exactly what
splitting a 90-wide grid by parity produces, not evidence of two fields.

**The ground truth arrived (6.7b).** The party's cell is now readable and `0xCD` is
established as blocking, which corrects the "uninitialised fill" reading below: however
those bytes got there, the game treats them as terrain it refuses to enter.

**Evidence:** connected-component counts over `cont1.fic` and `cont2.fic`; the parity-plane
comparison over three files.

### 6.7b Where the party is, and what stops it (T11g3)

**The party's map cell is the two bytes immediately after the resident map grid.** Found
by snapshotting all 64 KB from SS across driven steps and keeping the bytes that move by a
constant amount: Up and Down move `ss:[0x644c]` by +1/-1, Left and Right move `ss:[0x644d]`
by +1/-1, and neither key touches the other byte.

Those are the addresses as seen from SS, and the SS-relative form is incidental. What they
actually are is structural: `ss:[0x644c]` is linear `0x13ccc`, and the level grid sits at
`0x129d0` and is 4,860 bytes long -- so it ends at `0x13ccc` **exactly**. The row and column
are the first two bytes past the grid, in the same block. That is also why the listing has
no `ss:[644c]` reference anywhere: the address is allocated, not linked.

**A new game starts at row 11, column 29 of `cont1.fic`** -- region 0, FRAGONIR, on a cell
whose value is `0x00`, with the NPC of 4.17 a few steps north. Read on two separate cold
boots, and it is the cell the gate and the murder consequence both return the party to.

**So movement is absolute, not relative.** The arrow keys are north/south/east/west, and
the party does not turn -- which is why T29f's "six forward steps per turn" ended against a
hedge, and why the earlier probe that demanded a coordinate change of exactly +-1 after a
*turn* found nothing.

**The grid is indexed `row * 90 + col`.** The alternative orientation puts the walked path
outside the map. Confirmed against the level in memory: `cont1.fic` is resident at linear
`0x129d0`, matching the file byte for byte, so the game keeps the grid verbatim -- a
rewrite can read `cont*.fic` straight off disk with no transform.

**`0xCD` is impassable and nothing else observed is.** Attempting all four moves from a
series of cells and reading `0x644c`/`0x644d` afterwards separates refused from accepted:

| | count | cell values |
|---|---|---|
| refused (blocked) | 4 | `0xCD`, `0xE6` |
| accepted (walkable) | 20 | `0x00`, `0x03`, `0x04`, `0x05`, `0x06`, `0x13`, `0x14`, `0x15`, `0x16`, `0x18`, `0x1b`, `0x1f` |

The two sets are disjoint over 38 move attempts across 38 cells. Four refusals is a thin
sample and is stated as such, but a refused move is unambiguous -- the coordinate simply
does not change.

**`0xCC`/`0xCD` are water.** Three things agree and none of them is the byte value:

1. Every refused move targeted one (above).
2. **Rendered, they are hydrography.** `captures/map-cont1.png` colours the classes: the
   `0xCC`/`0xCD` regions branch like a river system, run continuously across the landmass
   and terminate against the `0xCE` outline -- 182 of their edge neighbours are `0xCE`.
   An uninitialised-memory artefact does not braid.
3. The player remembers impassable water in Ishar.

The old reading -- "outside the playable area, the MSC uninitialised-memory fill" -- came
from the byte values `0xCC`/`0xCD` being that compiler's fill pattern. That is a real
coincidence and it was taken for an explanation. FORMATS 3.12 is corrected.

**`0xCE` is the shoreline** and it encloses each landmass: one cell wide, mean 1.96-1.99
orthogonal same-value neighbours in all six files, and it is what the water runs into.

**`0x9D` is the interior fill of the built structures.** `cont2` holds a walled town in its
left half and `cont5` is almost entirely one walled fortress (`captures/map-cont2.png`,
`captures/map-cont5.png`); in both, the enclosure is drawn in values `0xDF`-`0xE2` and the
space inside it is `0x9D`, 440 of whose 600-odd edge neighbours are itself. Not walked on
yet, so this is a reading of the rendering, not a measurement.

**The six grids are separate regions, not tiles of one world.** Testing every edge of every
file against every other edge for terrain-class continuity produces no non-degenerate match:
the only 100% scores are `cont5`'s right column against `cont4`'s left, which are both 54
cells of solid `0xCE`, and anything involving `cont6`, which is 97% zero. Each region is
closed by its own `0xCE` outline, so movement between them has to be scripted -- which is a
lead for `telep.io` (*téléportation*).

**Bit 6 separates the two populations, exactly.** FINDINGS 6.7 split the values into
scattered singletons and large blobs by counting connected components. The split is not
statistical -- it falls on `0x40`:

| | mean component size | values |
|---|---|---|
| `0x00`-`0x3F` | **1.17 - 1.36 cells** | 24-35 per file |
| `0x40`-`0xFF` | **11 - 55 cells** | 5-16 per file |

Across `cont1`-`cont5` the only value below `0x40` that forms blobs is `0x00`, the base
(plus `0x28` in `cont2`), and the only ones above it that do not are the building-wall
values `0xDF`-`0xE2` and `0x64`-`0x67`, which are one-cell-wide lines because that is what
a wall is. **So the low half is per-cell objects and the high half is area terrain**, and a
rewrite can branch on `value & 0x40` before looking anything up.

**The tile sets are per region.** Only **five** values occur in all six grids -- `0x00`,
`0x0C`, `0x0F`, `0x10` and `0xCD`. `cont1` uses low values `0x00`-`0x39` and high ones
`0xAB`-`0xFF` with nothing between; `cont2` uses `0x00`-`0x3F` plus `0x40`, `0x50` and
`0x9D`-`0xE2`. Each region therefore carries its own meaning table, which fits its own set
of scene assets (`plaine.io`, `arbre.io`, `lacustre.io`, `rplaine.io` for `cont1`'s plains,
trees and lake). **A single global tile table would be wrong.**

**Not established**: no value has been tied to a specific sprite yet (T11g3d).

**Three side readings.** Several other DGROUP bytes track the party's row exactly
(`ss:[0x8716]`, `[0x9457]`, `[0x90a0]`, `[0x97dc]`, `[0x9cc6]`, `[0x9dfa]`, `[0x9e9a]`), so
the position is copied into more than one structure. Two more are *mirrors* of it --
`ss:[0x9962]` holds `40 - row` and `ss:[0x99f7]` holds `27 - row`, constant sums across
every step -- which is the shape of a distance from the party to a fixed scene object, and
therefore a lead for the viewport renderer (4.18). And the walked path crosses eight
distinct walkable values in eighteen cells, far too varied for "open ground", which is
consistent with 6.7's reading that low values are per-cell scenery markers.

**Confirmed across sessions.** After a full emulator restart and a fresh boot, `cont1.fic`
loads at the same `0x129d0` and the party's row is again at `grid_end` -- so the adjacency
is not allocation luck within one run. `tools/mappos.py` finds both from scratch rather than
hard-coding the address. Still untested: whether it holds for a *different* grid (T11g3c).

**They are a readout, not the master.** Writing a new row/col does not move the party: the
value sticks, the view does not rebuild, and subsequent moves are decided from somewhere
else. So these bytes are a copy the engine updates on each successful move -- which is
exactly what makes them a reliable instrument, and useless as a teleport.

**Evidence:** the DGROUP diff over five driven steps with the screen change (13-31% per
step) confirming each step happened; the four-direction refusal sweep over 38 cells
(`.ish/t11g3-walk.json`); the class renderings in `captures/map-cont{1,2,5}.png`; the
edge-continuity test across all six files; `cont1.fic` located in memory by a 64-byte probe and verified
across all 4,860 bytes. Tools: `tools/t11g3-pos2.py`, `t11g3-watch.py`, `t11g3-probe.py`.

### 6.8 How the language choice reaches a different file (T11e, partial)

The four language variants of a text asset are loaded by a **switch in `main.io`'s script**,
not by a name or a suffix rule. For the message files it sits at offsets 2874-2949:

```
2870  19 00 2a      cmp dx,cx; if equal skip to 13625 -- past the whole block
2874  0a 39 00 00   unconditional skip of 57 -> lands at 2935
2878  45 63 00 "messagee.IO"      English,  asset id 0x63
2893  0a 34 00 00   skip 52 -> 2949, the end of the block
2897  45 64 00 "messaged.IO"      Deutsch,  id 0x64
2912  0a 21 00 00   skip 33 -> 2949
2916  45 65 00 "messagei.IO"      Italiano, id 0x65
2931  0a 0e 00 00   skip 14 -> 2949
2935  45 0e 00 "message.IO"       French,   id 0x0e
2949  (continues)
```

Each case loads its file and then skips to the common end, which is a switch. **Running the
block from the top gives French** -- the first skip jumps straight to 2935 -- which fits a
French studio treating its own language as the fall-through. The same shape repeats for
`sos*` at 2974-3019 and for `textin*` at 11891-11977.

The skip opcodes are a family, all reading their displacement inline:

| opcode | handler | behaviour |
|---|---|---|
| `0x0a` | `seg_0000:273f` | `lodsw / inc si / add si,ax` -- unconditional forward skip |
| `0x17` | `seg_0000:28c0` | skip if `DX != 0` |
| `0x18` | `seg_0000:28cd` | skip if `DX == CX`, byte displacement |
| `0x19` | `seg_0000:28d8` | skip if `DX == CX`, word displacement |
| `0x1a` | `seg_0000:28e4` | as `0x18`, three-byte form |

`DX` is the VM accumulator (FORMATS 6), so these branch on whatever the preceding expression
evaluated to.

**What is established:** the four ids for each text asset, that the selection is a switch,
that French is the fall-through, and the opcodes that implement the skips.

**What is not:** what sets the entry point. Reaching the English case at 2878 requires `SI`
to arrive there, and nothing in the block does that -- linear execution always lands on
French. The selector is upstream and has not been found, so **which variable holds the
language, and where the menu writes it, are still open** (T11e2).

**Evidence:** the byte sequences above read from decoded `main.io`; the skip targets
computed from each operand and confirmed to land exactly on a load instruction or on the
block's end; the handlers read from `ishar-listing.txt`.

### 6.9 The language menu is script, not code (T08)

Displaying the language menu reads **no files at all**. Tracing INT 21h across the whole
stretch -- Silmarils logo to title screen to menu, and then across the menu keypress --
records **0 DOS file calls in 70 seconds**. Everything it needs is already in memory.

It is not hardcoded in the executable either. Sampling the interpreter's program counter
while the menu is on screen puts `DS:SI` at **`main.io` offsets 17410-17415**, ten samples
in a row, immediately after the menu's own strings at 17299-17396 (FORMATS 7.2). So:

- the strings live in `main.io` (`"1 - ENGLISH"`, `"2 - FRANCAIS"`, `"3 - DEUTSCH"`,
  `"4 - ITALIANO"`),
- the code that draws them is **also** in `main.io`, as VM bytecode, starting around 17410,
- and `main.io` was read once at boot (3.0), which is why the menu costs no I/O.

**This is the second verified entry point into a script**, after the one at 3270 that
established `main.io` is executed at all (FORMATS 7). Disassembling from 17410 produces
instruction boundaries at 17410, 17411, 17412, 17413 and 17415 -- exactly the offsets the
live program counter visited -- so the listing there is correctly aligned:

```
17410  38  vm_stmt_38
17411  6a  ...
17412  4a  vm_stmt_4a
17415  3a  vm_stmt_3a
17416  14  ... 0x0003
```

**Why `ishar.chani` gains nothing from this.** The database annotates the *executable*, and
the menu is not in the executable -- it is bytecode in an asset. The native side is only the
interpreter, which is already named (`vm_run`, `vm_dispatch`). What would belong in chani is
the routine that renders a glyph, which is still unfound (T13).

**Evidence:** `tools/gdbtrace.py` across the transition, 0 calls in 70.8s; ten consecutive
samples of `DS:SI` at the `vm_dispatch` fetch, each matched byte-for-byte into decoded
`main.io`; `captures/t08-language-menu.png` showing the menu on screen at the time.

### 6.11 The global variable area, field by field (T59)

The VM's globals are one flat byte array based at the far pointer `ss:[0bf6]`
(`126b:02a0` = linear `0x12950`). Three fields in it were named before this task -- the
map grid, the party's row and column, and the region id. `tools/t59-globals.py` names
seventeen more by snapshotting 32 KB of the area, performing one labelled action, and
snapshotting again.

**The method's control is an action that does nothing.** Seventeen bytes move with no
input at all; subtracting them is what makes the rest legible. Twelve to fourteen bytes
move on an `idle`, against roughly 1,300 on a single step.

| offset | holds | how it was established |
|---|---|---|
| `+0x0080` | the 90x54 map grid, 4,860 bytes | 6.7b |
| `+0x137C` | party row | changes by one on Up/Down, eight samples |
| `+0x137D` | party column | changes by one on Left/Right, eight samples |
| `+0x137E` | **not the facing** | constant at 2 across six moves in two axes |
| `+0x150C` | **the party roster: 8-byte name slots, one per member** | `+0x1514` went from zeros to `BORMINH` when he joined (6.13) |
| `+0x1746` | **the character-name table: 33 entries of 8 bytes** | the names read as text |
| `+0x2D68` | a second, byte-identical copy of that table | compared, 256 bytes equal |
| `+0x3646` | party row, echoed | tracks the row, eight samples |
| `+0x3EAC` | region id, 0..20 | 4.19b |
| `+0x3FD0`, `+0x3FD1` | party row and column, echoed as a pair | eight samples |
| `+0x4387` | **the row the party came from** | after a Down step from row 20 it reads 20, not 18 |
| `+0x438B` | ~~step counter~~ -- advances with moves in one session, not in another | 6.12 |
| `+0x438C` | ~~carries from `+0x438B`~~ -- jumped 135 on a RECRUIT with no carry | 6.12 |
| `+0x4392` | **the current region's name as text**, `FRAGONIR` | string match, with `+0x3EAC` = 0 |
| `+0x470C`, `+0x470D` | party row and column -- **dialog scratch, not a record** | eight samples; gone once another dialog ran |
| `+0x472E` | `ARAMIR` -- **dialog scratch**; the name the open dialog was about | string match; replaced by `BORMINH` at a different offset |
| `+0x4736` | `OSGHIROD` -- dialog scratch, the region ORIENTATION had reported | string match |
| `+0x4892` | `40 - row` | eight samples |
| `+0x4927` | `27 - row` | eight samples |
| `+0x4B58`, `+0x4BF6`, `+0x4C96` | `(row+1, col+1)` pairs, ~0xA0 apart | eight samples |
| `+0x4D36` | a `(row, col+1)` pair | eight samples |
| `+0x5C00`..`+0x7C00` | rewritten wholesale on every redraw | ~1,300 bytes per step |

**The name table is the content of the game's cast.** Thirty-three eight-byte slots at
`+0x1746`: XYLAZ, ZELORAN, KYRIAN, TARGHAN, ARAMIR, DORIAN, FHIRONN, UNKNOWN, GAARTH,
KARORN, GOLNAL, KHALIN, SHEELDA, BROM, AZIREK, STILMAR, YORNH, FONAHIR, KLESH, BOROMAN,
OBARMON, NASHEER, MOLGO, AKORMH, MOGH, MYRIELH, UNKNOWN, DELORIA, BORMINH, MORGULA,
KIRIELA, FRAGORN, MANATAR. Slots 7 and 26 read `UNKNOWN`, which is a placeholder the game
ships rather than an empty slot.

**Slot 28 is BORMINH** -- the NPC two steps from the start, whose sprite is `bormin.io`
(4.15f). The asset name and the character name agree, which is the first link between the
two.

**A field that tracks the party is not necessarily the party's.** Seven places hold the
party's cell, at four different offsets from it. Three carry it verbatim, three carry
`(row+1, col+1)` and one `(row, col+1)`. Only `+0x137C` is known to be the one the engine
acts on: writing the copies at `+0x137C` was already shown to change a readout and not a
position (see the scar in `CLAUDE.md`), and nothing here says which copy is authoritative.

**And a field that tracks the party is not necessarily a field.** The table above once
called `+0x470C`/`+0x470D` the party's cell "inside the leader's record", because `ARAMIR`
sat `0x22` bytes further on. That is struck: there is no leader's record there. Recruiting a second character (6.13) emptied all of it: the name
went, the cell went, and `BORMINH` appeared 138 bytes earlier with the same surrounding
shape. The whole block is **the open dialog's rendered content** -- the ORIENTATION panel
an earlier session had left up, whose subject was ARAMIR, whose party cell it was showing,
and whose answer was OSGHIROD. Eight snapshots agreeing was a real measurement of a buffer
that happened not to be rewritten in between.

**Evidence:** `tools/t59-globals.py`, four runs against one emulator session. Every
coordinate claim is an exact fit of `v = +-1 * row + b` or `+-1 * col + b` across eight
snapshots spanning four rows and four columns, which a constant or a timer cannot
satisfy. The party's own row and column are re-derived by the same test, as the control.
Each run reports the viewport's change percentage, because the tool's first run spent six
actions inside a modal dialog an earlier session had left open and measured its timers as
state (`captures/t59-modal-dialog.png`).

### 6.12 ~~Ishar's clock runs on footsteps~~ -- the pair at `+0x438B` is not a step counter (T64)

**This section said `+0x438B`/`+0x438C` were a step counter and that is struck.** The
claim was written from one session, and the next session contradicted it. What follows is
both observations, because the first one is still a real measurement and the model built
on it was not.

**Session one, a game that had been played for a while.** `+0x438B` read 3, 3, 4, 0, 1, 2,
3, 4 across seven actions -- one increment per move, wrapping at five -- while `+0x438C`
read 16, 16, 16, 17, 17, 17, 17, 17, carrying exactly when the low byte wrapped. Six moves,
six increments, no increment on the idle. Then four waits of ten seconds each left both
bytes unchanged and the very next step moved both.

**Session two, a fresh game.** Both bytes start at 0. The first step makes it 1/0. After
that the pair sat at 1/135 through **nine further moves in three directions**, with the
party's row and column changing on each and the emulator healthy.

**And it jumped by 135 on a RECRUIT**, with no step taken and without the low byte
wrapping -- which the carry model forbids outright.

So the pair counts something that a move advanced six times in one session and never in
another. It is not the number of steps, and it is not seconds either. T64 is reopened.

The honest reading of session one is that the low byte advanced *alongside* movement, not
because of it. Whatever the real driver is, it was active then and is not now.

**Evidence:** `tools/t59-globals.py idle fwd fwd fwd left left left` and
`tools/t59-globals.py wait10 wait10 wait10 wait10 fwd` for session one;
`tools/t60-record.py snap` after each of nine moves in session two, each snapshot printing
the party's cell alongside the pair, with `tools/ish status` showing cycles advancing
throughout.

### 6.13 The party roster, the character sheet, and the team vote (T60)

Recruiting the starting NPC settles what is a character record and what is not.

**The roster is at `+0x150C`: 8-byte name slots, one per party member.** `ARAMIR` sits in
the first. Before the recruit the next eight bytes were zero; after it they read
`BORMINH`. Nothing else in 64 KB of the global area went from zero to a name.

**BORMINH is the NPC two cells from the start**, slot 28 of the name table at `+0x1746`
(6.11), and his sprite is `bormin.io` (4.15f).

**The character sheet names the attributes.** Aiming RECRUIT at him shows a panel before
any commitment (`captures/t60-borminh-sheet.png`):

```
BORMINH
THIEF
HUMAIN
LEVEL        : 1
STRENGTH     : 7
CONSTITUTION : 6
AGILITY      : 8
INTELLIGENCE : 6
```

So a character has a name, a **class**, a **race**, a level and four attributes. `THIEF`
and `HUMAIN` are resident as text at `+0x4FA8` and `+0x4FBA`, in an otherwise empty region
-- scratch the panel was rendered from, not a record.

**The attribute values are not in the global variable area.** 1, 7, 6, 8, 6 does not occur
in 64 KB at any stride from 1 to 8, nor does any byte sequence whose values divided by ten
give them. So character stats live somewhere else, and T60's remaining half is finding
where -- the roster is a list of names, not of records.

**Recruiting is put to a vote.** Committing the panel does not add the member; it opens a
second panel reading `TEAM VOTE :`, then one line per existing member, then the outcome
(`captures/t60-recruited2.png`):

```
TEAM VOTE :

ARAMIR       : OK

MEMBER RECRUITED
```

With one member there is one vote. What a member's vote depends on is unknown, and it is
the first mechanic found here that reads party state rather than world state.

**Evidence:** `tools/t60-record.py`, snapshots either side of the recruit against one
emulator session booted fresh to the start cell; `+0x1514` is the only zero-to-name
transition in the diff. The panels are `captures/t60-borminh-sheet.png` and
`captures/t60-recruited2.png`, and `captures/t60-party2.png` shows both portraits and both
LIFE bars afterwards. The attribute search is a stride scan over the 64 KB snapshot taken
while the sheet was on screen.

### 6.14 A portrait opens an inventory, and nothing found closes it

Clicking a character's portrait replaces it with that character's inventory: a slot grid
with a left and a right hand, and ARAMIR starts with a sword in the left
(`captures/t60-inventory.png`).

**While it is up the party cannot move.** All four arrow keys are refused, which reads as
a hung game -- `tools/walkto.py` reports `no route` with every direction learned blocked.

Escape, a second click on the portrait, a right click, and the red square in the panel's
corner were each tried and none closed it. Recovering cost an emulator restart.

**Evidence:** four move attempts, each read from the position bytes; the four close
attempts above; `captures/t60-inventory.png`.


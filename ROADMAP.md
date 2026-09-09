# Ishar — roadmap

Ordered, checkable tasks. Each is sized for one session and each has a **Done when**
that can be verified without discussion — that is what makes it safe to hand to `/goal`
and walk away.

Copy a task's title and Done-when into `/goal` to run it. Everything a task needs lives
in its entry — there is no second place to look, deliberately: separate brief files were
tried and one of them rotted into stating a disproved premise as verified fact.

Every task that produces an address -- a routine, a table, a call site -- ends with that
address annotated in `ishar.chani`, not only written up in `FINDINGS.md`.

Status: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

**Next up: T10 → T11 → T18, then T09.** T10 is the cheapest thing on the board and unblocks the
most: T07 located the one path every asset takes, so the decoder is a read of known
code rather than a search, and each measurement is a ~10s run from a paused start —
short enough that the crashes barely bite. T11 turns that into a decoder with test
vectors, which is what text, sprites and maps all wait on. T18 comes straight after,
because two distinct garbage-execution faults cost runs in a single session and that
tax lands on every task after this one. Bring T18 forward immediately if a crash costs
a second run before then. T09 follows T11 because the decoder changes how it is done
(below). T09b needs no emulator at all and can fill any gap.

The arc: get the binary readable, learn what the game loads and when, then reproduce
two real screens offline from the game's own files. Reproducing a screen is the first
honest proof that the formats are actually understood, and it is directly the thing the
Compose rewrite has to do.

---

## M1 — Make the binary readable

- [x] **T01 · Annotate the unpacker stub**
      Follow the entry stub at `+0x0003` through the upward relocation and into the
      decompressor; annotate both in `stub.chani`.
      **Done when:** `stub.chani` is committed, `disasm` renders the whole stub and the
      decompressor as code with no `db` runs inside them, and FORMATS.md §1.2 describes
      the compression scheme.

- [x] **T02 · Transcribe the unpacker**
      `tools/unpack.py` rebuilds `start-unpacked.exe` — a real MZ with a rebuilt
      relocation table — as a transcription of T01, with the stub's own structural
      invariants asserted.
      **Done when:** it runs clean, and running it twice produces byte-identical output.

- [x] **T03 · Prove the unpack**
      `tools/verify-unpack.py` runs the *shipped* `start.exe` under Spice86, breaks at
      the real entry, applies relocations at the observed load segment, compares.
      **Done when:** it prints `IDENTICAL` over the whole image, and FORMATS.md §1 is
      **Status: specified** with both sha1s pinned. *Nothing static is trustworthy
      before this passes.*

- [x] **T04 · Segment map and listing baseline**
      `tools/segmap.py` derives segments and code seeds from the rebuilt relocation
      table; `ishar.chani` covers launcher (`+0x0000`) and game (`+0x9410`);
      `tools/disasm.sh` + `cover.py` render and measure.
      **Done when:** `tools/disasm.sh` prints a coverage figure, and a runtime address
      seen in Spice86 maps to a listing address with no arithmetic done by hand.

- [x] **T05 · Symbol bridge**
      Convert Spice86's executed-function catalogue (`list_functions`) into chani
      annotations, so everything the emulator has actually run starts life marked as
      code.
      **Done when:** one boot-to-gameplay run's functions are imported and coverage
      moves; the delta is recorded.
      *Done: `tools/symbols.py`. Two runs merged (language menu, then gameplay),
      265 seeds, coverage 8.2% → 27.9%.*

## M2 — Learn what the game loads, and when

- [x] **T06 · `tools/ish` — the measurement harness**
      Deterministic launch (sync rendering, fixed clock, dummy audio), one command in /
      one structured result out; `start/stop/status/regs/mem/dis/bp/run-until/step/
      keys/shot`. `shot` writes straight into `captures/` with a given name.
      **Done when:** `tools/ish boot` reaches gameplay unattended and `tools/ish status`
      distinguishes running, paused and faulted.
      *Done: boot reaches gameplay in ~11 nudges, verified by the party panel being
      pixel-identical to a reference; status shows running / paused / faulted, the last
      induced by pointing INT 8 at video memory.*

- [~] **T07 · File I/O trace: launch → language menu**
      Break on `INT 21h` open/read/seek/close and log every call: file name, order,
      offset, length, destination buffer.
      **Done when:** FINDINGS.md has a table of every file touched before the language
      menu appears, in order, with sizes — and the same run twice gives the same table.
      *Traced launch → `logo.IO` (18 calls, FINDINGS §3.0), reproducible across runs,
      with every caller located and annotated in `ishar.chani`. Remaining: the menu
      transition, which needs a keypress — nudging over MCP pauses the emulator too
      often to trace through it, so this wants a two-phase run (trace to the logo,
      detach, nudge, re-attach).*

- [!] **T08 · File I/O trace: language menu → first in-game screen**
      Same instrument, next phase. Note which files are re-read per language.
      **Done when:** the table is extended through the intro to the first gameplay
      frame, and the per-language files are identified by diffing an English run
      against a French one.
      *Blocked: the menu needs a keypress, and driving keys while tracing costs more
      than it buys (3.5s → 27s → 61s as the nudge loop ticks faster; see CLAUDE.md).
      Moving keys to a separate process was the right shape but that run died on a new
      emulator fault — "Instruction requires a memory operand but encoding selects a
      register", i.e. execution in garbage again, a sibling of §5.1. Next attempt should
      be two-phase: drive to the menu and select the language over MCP with no GDB
      client attached, then attach the tracer for the intro → gameplay stretch.*

- [ ] **T09 · Name the files** — *do after T11; the method has changed*
      For each file, say what it is: splash image, menu font, text block, sprite set,
      map. Evidence is *when it is loaded and what is drawn next*, or — once T11 lands —
      what the decoded bytes actually are.
      *Originally this meant tracing every load, which is why it sat behind T08. Only
      three assets have been seen to load so far (`blancpc.io`, `MAIN.IO`, `logo.IO`)
      out of 108 files, so tracing would be a long road. After T11 the catalogue can be
      built offline by decoding all 108 and looking at them — dimensions and palette for
      an image, printable runs for text — with the traced load order confirming the few
      we have watched. Faster, and it covers the files no boot path ever touches.*
      **Done when:** FORMATS.md §3 carries a catalogue with a confidence marker per
      entry, every guess marked as one, and the three traced files agreeing with what
      the decoder says they are.

- [x] **T09b · Read the `START.STP` parser**
      `seg_13d7:0e9f` opens it and `seg_13d7:0eb4` reads 14 bytes to `1554:0386`; the
      parser is right there, and the same segment holds the setup screen's text.
      **Done when:** FORMATS.md §2 stops saying "Verified by: nothing" — each letter
      pair is named from the code that reads it, or explicitly marked unread.
      *Done: §2 is **specified**. Seven key/value pairs, all seven key letters validated
      by the parser; video/sound/keyboard decode to named enums, port/joystick/mouse are
      digits minus '0'. `R`'s value is never read — recorded as such. The old guess-table
      had two of seven right and invented a field.*

- [ ] **T09c · The launcher's setup screen**
      The `START.STP` buffer is followed by `VIDEO`, `CGA`, `EGA` and "to select
      options, ENTER to validate", so the launcher has a setup UI nobody has seen.
      **Done when:** FINDINGS.md says how it is reached (a key, a switch, a missing
      file), with a screenshot in `captures/` if it can be reached at all.
      *Lead from T09b: `load_settings` jumps to `0x0fde` and sets `settings_invalid`
      (`seg_13d7:0b90`) whenever START.STP is missing, unreadable, or fails the key-letter
      check. The setup UI's text sits in the same segment. Try it with the file renamed
      or a byte corrupted — copy it aside first, it is the game's own file.*

- [x] **T09d · ~~Why the scancode table differs on disk and in memory~~** — *withdrawn:
      there was no difference.* The listing was reading 0x250 bytes off, because
      `tools/segmap.py` mapped image offsets onto a file that still carries its MZ
      header. `seg_0000:04be` now reads `1b 26 82 22 …`, matching memory exactly. The
      task existed only to explain my own bug; the fix and the scar are in CLAUDE.md,
      and listing coverage rose 28.2% → 31.9% once decoding aligned with real code.

## M3 — Draw the language-selection screen ourselves

- [~] **T10 · Find the decompressor**
      From T07's destination buffer, follow the code that fills it.
      *Done: a byte-oriented RLE decoder and its stream helpers are annotated
      (`rle_decode_loop`, `get_byte`, `read_next_chunk`, `put_byte`, `load_container`,
      FORMATS §3.2), and the 16-byte header turned out to be a directory of counts, not
      compressed data. Remaining: prove `main.io` uses this decoder — a breakpoint on it
      never fired during a boot that loads the file, and there are two other chunk
      readers at `0x7bab` and `0x7d38`. The tracer needs to read one level further up
      the stack to name the outer caller.*
      *Cheaper than written: T07 located the single path every asset comes through —
      `after_dos_open` `seg_0000:1feb`, `after_dos_read` `seg_0000:2136`,
      `after_dos_close` `seg_0000:20be`, all annotated. The decoder is upstream of
      `:2136`; no search needed, and it does not need the menu traced.*
      **Done when:** the routine is annotated in `ishar.chani`, and the input bytes and
      the decoded bytes for one small file are captured side by side.

- [x] **T10b · Name the outer caller of each DOS call**
      The tracer reads the INT frame, so every caller comes back as `dos_read_asset`
      itself. One level further up the stack names the routine that wanted the file.
      **Done when:** a traced load of `main.io` and of `logo.io` each name the routine
      that drove it, annotated in `ishar.chani`, settling which of the three chunk
      readers is real.
      *Done: both files refill through `0x7bb1` then `0x7d3e` — two decoders in
      sequence — and neither touches the helper T10 had annotated. `main.io` carries the
      16-byte directory, `logo.IO` does not. FORMATS §3.3.*

- [ ] **T11b · What is actually inside a decoded asset**
      Decoding gives bytes; the rewrite needs to know what they *mean*. The 6-byte
      header and the decoder's plane count (`ss:[0b57]`: `0x80`→1, `0xa0`→2, else 8)
      are the colour-depth story, but nothing yet says the dimensions, the plane
      layout, or where the palette comes from — the questions a CPS file answers with
      "320x200, 256 colours, palette inline".
      **Done when:** FORMATS.md states, for one decoded image asset: width, height,
      bit depth, plane order, and whether the palette travels with the file or comes
      from elsewhere — each derived from the code or from a byte-for-byte comparison,
      not from the picture looking right.
      *Thread from T09b: `cfg_video` distinguishes CGA, EGA, VGA and Hercules, and the
      decoder's plane count is 1, 2 or 8. Those two sets probably line up — 1 plane for
      Hercules, 2 for CGA, 8 for VGA — which would mean a file carries several
      representations, or the loader picks a variant. Check before assuming: the game
      ships configured for VGA and we have only ever watched it in that mode.*

- [x] **T11c · Decode the 6-byte header field by field**
      Every asset starts with it; `load_container` reads it to `ss:2480` before
      anything else, and `ss:[0b57]` (the plane selector) is one byte of it or derived
      from it.
      **Done when:** each of the six bytes is named in FORMATS.md with the code that
      reads it, and the values for `main.io`, `logo.IO` and `blancpc.io` are tabulated.
      *Done: three words — size, mode, and a catalogue discriminator (FORMATS §3.0),
      each named from the code that consumes it and checked across all 106 files. Also
      kills the "11-byte signature" guess: there is no signature.*

- [ ] **T11d · Where the settings actually take effect**
      T09b named `cfg_video`, `cfg_sound`, `cfg_keyboard` and the rest, but only where
      they are *written*. What reads them is the interesting half: `cfg_keyboard` should
      lead to the code that builds `scancode_to_char`, and `cfg_video` to the mode set.
      **Done when:** each `cfg_*` has its readers listed in `ishar.chani`, and the
      keyboard one is followed as far as the table build — which is what a rewrite needs
      in order to offer layouts at all.

- [ ] **T11f · The four `.fic` files with an all-zero header**
      `cont1`, `cont2`, `cont6` and `en1` have six zero bytes where every asset has a
      header, so they are probably a different format — and `cont1..6` are all exactly
      4860 bytes, which smells like fixed-size records.
      **Done when:** FORMATS.md says what they are, or states plainly that nothing in
      the code reads them as assets.

- [ ] **T11e · Decode main.io's catalogue and answer the language question**
      Assets are fetched by numeric id through an index in `main.io` (FORMATS §3.4), so
      the id→file mapping lives in its data, not in the code. The per-language files
      (`textin`/`textind`/`textine`/`textini`, `sos`/`sosd`/`sose`/`sosi`,
      `messagee`/`messagei`) are presumably separate ids, or one id whose record varies
      — and the language menu picks between them somehow.
      **Done when:** the catalogue's record layout is in FORMATS.md, the id of at least
      one known file is confirmed against a live load, and FINDINGS.md states how the
      language selection reaches a different file — with the code or the trace that
      shows it, not the filename pattern.

- [ ] **T11 · `tools/io.py`**
      Port the decoder offline.
      **Done when:** it reproduces the emulator's decoded buffer byte for byte for ≥4
      files including the largest (`iboishar.io`) and one `.fic`.

- [ ] **T12 · Palette**
      Capture the DAC at the language menu; establish where the palette comes from —
      part of the asset, a separate file, or code.
      **Done when:** FORMATS.md states the palette source, and a decoded image rendered
      with it matches the emulator's colours.
      *An asset carries colour indices only; the palette is loaded separately, and the
      wrong one gives a correct picture that looks broken.*

- [ ] **T13 · The menu's glyphs**
      The language menu's text is drawn in stylised glyphs, so there is a font asset and
      a text routine. Find both.
      **Done when:** the glyph set is decoded to a PNG sheet in `captures/`, and the
      routine that places them is annotated.

- [ ] **T14 · Reproduce the language screen offline** ← *the first real proof*
      Compose the screen from the game's own files with `tools/io.py`, the palette from
      T12 and the glyphs from T13. No emulator.
      **Done when:** the rendered PNG is pixel-identical to
      `captures/menu-language.png`, or every differing pixel is explained in writing.

## M4 — Draw the first in-game screen

- [ ] **T15 · Inventory the first frame**
      Which assets compose it: backdrop, party panel frame, portraits, compass, LIFE
      bars, ACTION/ATTACK buttons.
      **Done when:** each element is traced to the file it comes from, recorded in
      FINDINGS.md against `captures/game-party-panel.png`.

- [ ] **T16 · Layout and layer order**
      Coordinates and draw order for those elements; how the panel is composited over
      the view.
      **Done when:** FORMATS.md carries the geometry as numbers, derived from the code
      rather than measured off a screenshot.

- [ ] **T17 · Reproduce the first in-game screen offline**
      **Done when:** the rendered PNG matches `captures/game-party-panel.png`, or every
      difference is explained. At that point the asset pipeline is proven end to end and
      the CMP work can start against `FORMATS.md` alone.

## M5 — Foundations for mechanics

- [ ] **T18 · Root-cause the INT 8 crash**
      **Scheduled third, after T11** — promoted out of "foundations for later" on the
      evidence of 2026-09-08/09: two distinct garbage-execution faults (§5.0, §5.1) cost
      four runs in one session, and every measurement task after this one pays that tax.
      Do it sooner if a crash costs a second run before T11 lands.
      **Done when:** every write to the vector across a boot-to-crash run is recorded
      with its writer, and the cause — or the exact trigger — is stated with evidence.
      *Method: `watch-int8.sh` exists but attaches after boot and has never seen an
      install. Start paused (`ish start --gdb --pause`) and break on writes to
      `0000:0020..0023` from cycle zero, recording each writer's `CS:IP` and whether it
      writes a full far pointer or only half. `seg_0941:1c31` runs `mov ax,3508 / int 21`
      (DOS get-vector for INT 8) and `seg_0000:0d98` is the launcher's handler, whose
      offset is the one in the failing vector — both are the obvious suspects.*

- [ ] **T19 · Character record and levelling**
      **Done when:** every field is named or explicitly marked unknown, the XP curve is
      written as data, and one prediction stated in advance is confirmed in the game.
      *Method: locate one member's HP by taking damage and intersecting `search_memory`
      results across two or three observations; find a second member the same way, and
      the base and stride of the array fall out. Then `MEMORY_WRITE` breakpoints on the
      HP field for the damage routine, on XP for the award, on level for the level-up —
      which will index a threshold/gain table that is the levelling spec. Verify by
      predicting a value before an action, not by reading one after.*

- [ ] **T19b · Characterise the second garbage-execution fault**
      `Instruction requires a memory operand but encoding selects a register` killed a
      traced run (FINDINGS.md §5.0). Distinct symptom from §5.1, same family.
      **Done when:** FINDINGS.md §5.0 says whether it is the same root cause as §5.1
      or a second one, with the faulting address and how execution got there.

- [ ] **T19c · Re-seed the four routines chani cannot lay out**
      `seg_0000:072d`, `seg_0000:0d98`, `seg_0941:1299`, `seg_0941:1c31` are real
      routines dropped from the listing because chani panics on them — and `0d98` is
      the launcher's timer ISR, wanted by T18.
      **Done when:** each is readable somewhere — a chani workaround, a patched
      chani-rs, or a `read_disassembly` transcript pasted into `ishar.chani` as a
      comment — and none is silently missing.

- [ ] **T20 · Input map**
      Which keys and mouse actions the game accepts in each state, from the handler
      rather than from experiment alone.
      **Done when:** FINDINGS.md §2 lists them per screen, and the mouse question
      (§2.2) is answered.

---

## What changed as we learned

- T10 no longer needs a search: the asset path is three annotated addresses (T07).
- T08 is blocked on driving keys during a trace, and is **not** on the critical path —
  M3 can proceed without it.
- Five new tasks came out of M2: T09b, T09c, T09d, T19b, T19c — of which T09d turned
  out to be a phantom, caused by the segment map being offset by the MZ header.
- T09 moved *behind* T11 rather than ahead of it: decoding 108 files offline beats
  tracing loads one at a time, and it reaches files no boot path touches.
- The crashes are now a tax on every measurement, so T18 is scheduled third rather than
  left in M5 — a flag saying "promote this if things get bad" is not a decision, and
  nobody re-reads a conditional.

## Sequencing notes

- T03 gates M2 onward in practice: reading code is painful without a listing, though
  T07 can be run before it if needed.
- T14 and T17 are the milestones that matter to you. Everything before them is
  scaffolding, and both are checkable by a machine, which is what makes them good
  unattended goals.
- M5 is deliberately last except T18, which gets promoted the moment the two-minute
  crash budget costs more than fixing it.

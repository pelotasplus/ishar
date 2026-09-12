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

**Next up: T37.**

The graphics and text formats are solved -- 803 sprites extract with correct geometry, the
palettes are located, the strings are readable in four languages, and a reader written from
FORMATS.md alone reproduces the extraction byte for byte (9.6).

What is not solved is **behaviour**, and it is a single blocker rather than many. Only 42% of
asset bytes are accounted for; the rest is bytecode nobody can disassemble because no entry
point is known for any asset except `main.io`. That one gap is why `zombi.io` is half
unknown, why the language files are 88% unknown, why `affobj.io` is entirely unknown, and
why combat, magic and quests (T21-T24) have never been located.

T37 attacks it directly. T33, T34 and T32 are instances of it and should wait.

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

- [x] **T07 · File I/O trace: launch → language menu****
      Break on `INT 21h` open/read/seek/close and log every call: file name, order,
      offset, length, destination buffer.
      **Done when:** FINDINGS.md has a table of every file touched before the language
      menu appears, in order, with sizes — and the same run twice gives the same table.
      *BLOCKER LIKELY STALE (recheck before believing it): it was written before
      `tools/nudge.py` moved key-sending into a separate process, which is the documented fix
      for exactly this -- CLAUDE.md, "a blocking tracer and a key-sending timer cannot share
      one loop". Every probe since has driven the game that way while tracing.*
      *Traced launch → `logo.IO` (18 calls, FINDINGS §3.0), reproducible across runs,
      with every caller located and annotated in `ishar.chani`. Remaining: the menu
      transition, which needs a keypress — nudging over MCP pauses the emulator too
      often to trace through it, so this wants a two-phase run (trace to the logo,
      detach, nudge, re-attach).*
      *Met, and the "remaining" note was describing T08's scope rather than this task's.
      FINDINGS 3.0 has the table -- 18 calls from `START.STP` through `cd.tst`, `blancpc.io`,
      `MAIN.IO` and the findfirst probes to `logo.IO`, in order, with sizes and destination
      buffers, reproducible across runs, and every caller located and annotated in
      `ishar.chani`.
      The scope is "before the language menu appears", and the same trace establishes that
      nothing else is read: **after `logo.IO` closes the program makes no file call for at
      least 130 seconds** while the logo sits on screen. Whether the menu *transition* reads
      anything is the next phase, which is what T08 covers -- it was written into this entry
      by mistake and blocked it for months.*

- [x] **T08 · File I/O trace: language menu → first in-game screen****
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
      *Unblocked and half done. The stated blocker was stale: driving keys from a separate
      process (`tools/nudge.py`) traces fine, and the actual obstacle was simpler -- the menu
      takes **`Kp1`**, not `1`, because the top row needs `remap-digits.sh` (it is in
      `cmd_boot`'s docstring and was not read).
      Traced logo -> title -> menu: **presen.IO, preson.IO, presti.IO, iboishar.IO** load
      after `logo.IO`, then nothing. Displaying the menu and pressing a language both cost
      **0 DOS file calls in 70s** -- the menu is script inside `main.io`, already resident
      (FINDINGS 6.9).
      Remaining: the per-language diff. Nothing is re-read at selection time, so whichever
      `message*`/`textin*` variant is used must be chosen later, when the game proper starts.
      The trace has to reach the first gameplay frame to see it.*
      *Correction: only **half** the old blocker was stale. Key-driving was; the emulator
      fault was not -- it recurred on 2026-09-09 at `017D:194D` (FINDINGS 5.0), and three
      traced runs died in the intro before reaching gameplay. It was then misreported to
      the user as a long intro.
      But gameplay **is** reachable: the user got there in a plain `run.sh` session, so the
      fault is not inherent to the intro. That makes the next step a bisect, not a
      workaround -- find what the traced run does that a manual one does not (GDB attached,
      breakpoint armed, nudged keys, dummy audio, fixed clock), rather than assuming the
      path is impassable. `tools/gdbtrace.py` now aborts on the fault instead of running
      out its budget, so each attempt costs seconds rather than twenty minutes.*
      *DONE. Both halves. Two cold boots traced through to the Fragonir outdoor frame,
      one English one French, 34 opens each (FINDINGS 4.10), and the per-language diff is
      exactly two files: `messagee.IO`/`message.IO` and `sose.IO`/`sos.IO` (FORMATS 10.1,
      now confirmed live rather than inferred from the directory listing).
      What actually blocked it was never the emulator. Three things were:
      (1) `nudge.py` keys do not reach the game while MCP keys do -- 180s of Escape/Space
      moved nothing, `ish boot` was in the game in 16s with the same keys;
      (2) the language key was pressed at t=3s, ~85s before the menu exists;
      (3) the intro fault is intermittent (FINDINGS 5.3), so a trace has to be retried --
      `tools/t08run.sh` does that, and `gdbtrace.py` aborts on the fault in ~2s.
      Two corrections fell out: `EN1.FIC` is not English (both runs load it) and `textin*`
      is not a startup file at all.*

- [x] **T09 · Name the files**
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
      *Done, and honestly partial: 10 files are text with high confidence (read as real
      dialogue), 9 do not decode, and **87 are left explicitly unclassified** because
      nothing in their bytes has been shown to be an image yet — naming them from their
      filenames is the guess this project has been burned by twice. Two of the three
      traced files agree; `blancpc.io` is mode 0x00 and does not decode (T11g).*

- [x] **T09b · Read the `START.STP` parser**
      `seg_13d7:0e9f` opens it and `seg_13d7:0eb4` reads 14 bytes to `1554:0386`; the
      parser is right there, and the same segment holds the setup screen's text.
      **Done when:** FORMATS.md §2 stops saying "Verified by: nothing" — each letter
      pair is named from the code that reads it, or explicitly marked unread.
      *Done: §2 is **specified**. Seven key/value pairs, all seven key letters validated
      by the parser; video/sound/keyboard decode to named enums, port/joystick/mouse are
      digits minus '0'. `R`'s value is never read — recorded as such. The old guess-table
      had two of seven right and invented a field.*

- [x] **T09c · The launcher's setup screen**
      The `START.STP` buffer is followed by `VIDEO`, `CGA`, `EGA` and "to select
      options, ENTER to validate", so the launcher has a setup UI nobody has seen.
      **Done when:** FINDINGS.md says how it is reached (a key, a switch, a missing
      file), with a screenshot in `captures/` if it can be reached at all.
      *Lead from T09b: `load_settings` jumps to `0x0fde` and sets `settings_invalid`
      (`seg_13d7:0b90`) whenever START.STP is missing, unreadable, or fails the key-letter
      check. The setup UI's text sits in the same segment. Try it with the file renamed
      or a byte corrupted — copy it aside first, it is the game's own file.*
      *Done. It is "SILMARILS SETUP — by Julien Pierre" (FINDINGS 4.11,
      `captures/t09c-setup-screen.png`). Reached without touching the game's file at all:
      `tools/ish poke 1554:0e9f 9090` turns the `jnb` at `seg_13d7:0e9f` into two NOPs so
      the failure jump always runs. START.STP verified byte-identical afterwards.
      It paid for itself twice over — the on-screen choice lists confirm FORMATS 2's sound
      and keyboard enums from a direction independent of the parser, and corrected two
      details (QWERTZ**U**, and `I` = PC Speaker). VIDEO turns out to be displayed but not
      selectable.*

- [x] **T09d · ~~Why the scancode table differs on disk and in memory~~** — *withdrawn:
      there was no difference.* The listing was reading 0x250 bytes off, because
      `tools/segmap.py` mapped image offsets onto a file that still carries its MZ
      header. `seg_0000:04be` now reads `1b 26 82 22 …`, matching memory exactly. The
      task existed only to explain my own bug; the fix and the scar are in CLAUDE.md,
      and listing coverage rose 28.2% → 31.9% once decoding aligned with real code.

## M3 — Draw the language-selection screen ourselves

- [x] **T10 · Find the decompressor**      From T07's destination buffer, follow the code that fills it.
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
      *Met, and the remaining clause was resting on a dead premise. "Prove `main.io` uses this
      decoder" could never succeed: `main.io` is mode `0xa100`, so it takes the **LZ77** path
      at `seg_0000:7b85`, not the RLE decoder this task annotated. The breakpoint that "never
      fired" was a correct negative, and the task text simply was not updated when the mode
      branch was discovered -- the scar "read the branch before transcribing the routine" is
      about that exact mistake.
      The Done-when itself is satisfied by FORMATS 3.2: both decoders are annotated, and the
      input and decoded bytes are compared side by side for two files -- `main.io`, all 26,384
      bytes identical to the emulator's own buffer, and `logo.io`, 40,631 of 40,632.*

- [x] **T10b · Name the outer caller of each DOS call**
      The tracer reads the INT frame, so every caller comes back as `dos_read_asset`
      itself. One level further up the stack names the routine that wanted the file.
      **Done when:** a traced load of `main.io` and of `logo.io` each name the routine
      that drove it, annotated in `ishar.chani`, settling which of the three chunk
      readers is real.
      *Done: both files refill through `0x7bb1` then `0x7d3e` — two decoders in
      sequence — and neither touches the helper T10 had annotated. `main.io` carries the
      16-byte directory, `logo.IO` does not. FORMATS §3.3.*

- [x] **T11g · The nine assets that are not mode 0xa0**
      `tools/io.py` decodes 97 of 106. The rest are mode `0x00` (five, including
      `blancpc.io`, which is read whole and whose `hdr_size` equals its file size, so
      probably raw), `0x02` (two) and `0xcc` (two). The RLE decoder at `seg_0000:7a79`
      is already transcribed for these but has never been checked against ground truth.
      **Done when:** each of the nine either decodes byte-for-byte against a captured
      buffer, or is documented as a different format with the evidence.
      *Met, and the entry's premise was stale: the modes are `0xa100`/`0xa101`/`0xa102`
      (97 files, all decoding), and the nine failures are `0x0000` (5), `0x0204`, `0x03cc`
      and `0xcdcd`. `blancpc.io` is **mode 0 = stored** -- `hdr_size` equals the file length,
      so the payload is copied and comes out to exactly `out_len` with zero residue;
      `tools/io.py` now handles it, and all 106 files are accounted for. The other eight are
      `.fic` and are **not containers**: their first six bytes are data misread as a header.
      FORMATS.md 3.11.*

- [ ] **T20b · The manual copy-protection gate**
      `PROTECTION TEST-MANUAL`, `PLEASE USE YOUR MANUAL AND ENTER`, `WORD LINE`,
      `PAGE :` are in `messagee.io` (FINDINGS §3b), so the game asks for a word from the
      printed manual at some point. Automated play will hit it.
      **Done when:** FINDINGS.md says when it triggers, what it accepts, and where the
      check lives in the code — and whether a measurement session can get past it.

- [x] **T11i · Where an asset's geometry comes from**
      The width is not a word in the decoded header (checked for `logo.io`: 144, 88 and
      110 appear nowhere in the first 300 bytes), yet the game knows how wide to draw.
      Read the routine that blits a decoded asset — it takes the geometry from
      somewhere, and that is the authoritative answer rather than a width guessed until
      the picture stops shearing.
      **Done when:** FORMATS.md states where width, height and draw position come from,
      and `tools/io2png.py` derives them instead of taking `--width`.
      *Done: an 8-byte header immediately precedes each sprite's pixels, carrying
      width-1 and height-1 — the `[si+2]` the blitter reads. Verified on logo.io's
      144x118 sprite against the framebuffer, where every non-matching pixel was
      decoded 0x00 against the screen's background, establishing **colour 0 as
      transparent**. Draw position is not in the header; it comes from
      `ss:[0c2c]`/`ss:[0c2e]`. `tools/io2png.py --at OFFSET` now derives geometry.
      Remaining: how a sprite is located inside a file (T11k).*
      *Background (FORMATS §3.8): the drawing system is mapped — mode 13h, a swappable
      draw-target far pointer, a 320-byte stride, a rectangle blitter with clip bounds,
      and a sprite blitter that takes `[si+2]` as a dimension and steps an 8-byte header
      before the pixels. Draw position is `ss:[0c2c]`/`ss:[0c2e]`. What is still open is
      the width: it is not stored beside the pixels (searched), so it most likely lives
      in the `0x26`-byte descriptor the sprite blitter reads at `ES:DI+0x22`. Next step:
      decode those records — they are counted by `main.io`'s directory, so §3.5's
      catalogue work and this meet there.*

- [x] **T11k · How a sprite is located inside its file**
      **Partly answered from the other side:** sprites are 4bpp (FORMATS.md 3.10), which is
      why every static offset scan produced garbage and looked like a decoder bug.
      `tools/t11m-sprites.py` now captures real sprites from the blitter. Locating them
      inside a file is still open; the next lever is header word 3, which carries far more
      structure than a flag byte.
      Geometry comes from an 8-byte header (T11i), but finding the header still needs an
      offset. Walking from the first sprite works for two and then degenerates, so there
      is a directory. The file's first word is its own asset id from the catalogue,
      which suggests the head of the file is a keyed table.
      **Done when:** `tools/io2png.py` can enumerate every sprite in a file without being
      given an offset, and FORMATS.md describes the directory. **T11j found the same
      unknown from the other side** — the palette's offset is per-file too (992 in
      logo.io, nowhere near that in the others), so one directory answers both.
      *Also tried and failed: no decode start between `seg_0e97:04c0` and the call at
      `0531` lands on it, so the caller's entry is further back or the region interleaves
      data. Next: get the entry from the emulator by breaking at the call and reading the
      return address one level higher again, rather than searching for it statically.
      Progress: breaking on the draw confirmed sprites are reached by a normalised far
      pointer the caller holds (FORMATS §3.8), and the callers are `seg_0e97:0534` and
      `:055e`. Those sit mid-function in code the emulator's catalogue does not name, so
      the next step is to seed their enclosing routine and read where the pointer comes
      from. Four static routes ruled out and recorded in FORMATS §3.8: no offset table in the
      file head (the monotonic runs there are shading ramps), no offset in the catalogue,
      no general chaining (works for logo.io, fails for presen.io and dragon.io), and no
      palette. **Next attempt should ask the machine instead:** break on the sprite
      blitter around `seg_0e97:0330`, read `SI` when the logo draws, and subtract the
      decode buffer base — that gives the offset directly, and the logo appears about 13s
      into a boot, well inside the crash budget.*

- [x] **T11j · Where the palette comes from**
      `captures/asset-logo-verified.png` used the DAC as the emulator had it, which
      proves nothing about whether the file carries a palette. Ishar-era assets often
      ship indices only, with the palette loaded separately — the gunboat work was
      caught out by exactly this.
      **Done when:** FORMATS.md says whether a palette travels with an asset, and if not,
      which file or code supplies it, with the DAC writes traced to their source.
      *Done (FORMATS §3.9): the palette **is** in the asset — 256 RGB triplets, 8 bits
      per channel, and the game shifts each right by two for the 6-bit DAC. Verified
      768/768 against a captured palette. `seg_0000:74b5` copies it from the decoded
      asset into a staging buffer at `ss:0e46`; `seg_0e97:0d5f` writes that to port
      0x3c9. `tools/io2png.py --palette-at` uses it, so an asset now renders correctly
      with no emulator at all. The earlier "carries no palette" entry was wrong — that
      search looked for the 6-bit DAC values, not the 8-bit stored form. Where the
      palette sits varies per file, which is the same unknown as T11k.*

- [x] **T11l · Header word 3 — the depth/mode selector**
      Sprites captured live from the blitter render correctly at 4bpp; `logo.io`'s sprite
      at 1856 was verified byte-for-byte at **8bpp** (FORMATS.md 3.7). Both cannot be the
      default, so something per-sprite selects it, and word 3 of the 8-byte header is the
      only field left unexplained. Values seen live: 0, 16, 32, 128, 160, 162-165, 47872.
      *Method: the spacing between consecutive sprites in one buffer is a depth oracle that
      needs no emulator — 8 + w*h means 8bpp, 8 + w*h/2 means 4bpp. Correlate that against
      word 3 across the captured set, then confirm the winner against VRAM the way 3.7 did.*
      **Done when:** given a sprite header, `tools/io2png.py` picks the right depth on its
      own and reproduces the emulator's framebuffer for at least one sprite of each depth.

- [x] **T11o · `ish dis` resolves seg:off to the wrong bytes**
      `tools/ish dis 0e97:0380` printed data where `ishar-listing.txt` and both the live
      memory and the static image agree there is code. The live bytes at `seg_0e97:038b`
      match the image at file offset `0xef4b` exactly, so the listing is right and the
      command is wrong -- probably the same 0x250 MZ-header bias that bit `addr.py`.
      It cost a wrong turn during T11k.
      **Done when:** `ish dis 0e97:038b` prints the same instructions as the listing does.
      *Met. It passed the listing segment straight to Spice86 as a runtime segment, so
      `0e97` read bytes 0xe97 paragraphs from zero rather than from the program. A listing
      segment is an image paragraph, so the runtime segment is `load + seg`; `--runtime`
      now forces the old behaviour when a genuine runtime address is meant.*

- [x] **T11m · Why the colours are wrong on extracted sprites**
      The DAC is 16 sub-palettes of 16 (FORMATS.md 3.9) and a 4bpp index resolves as
      `base + nibble`. The full 768-byte palette is in the asset, 8-bit RGB, in a
      `fe ff 00 00` record (T11m4); the in-game DAC matched `fond.io @ 12108` and
      `geren.io @ 6684` 768/768 by exhaustive search.
      *This entry previously stated `group = word0 >> 8`, which **T11r disproved** -- the
      group is in word 3, and word 0's low byte selects one of five pixel formats. The
      wrong version is recorded here because it was believed for two sessions.*
      **Done when:** the pixel-exact confirmation -- superseded and met by T11r2, which found
      the code instead: `sprite_base_from_word3` (`seg_0e97:0b4c`) does `mov al,[si+6]` /
      `mov bh,al`, and `expand_4bpp` (`seg_0e97:0ad1`) adds BH to every nibble. An
      instruction that adds the base is a stronger statement than a pixel comparison, and it
      is not subject to the sprite scaling that made the framebuffer check fail.

- [~] **T11m2 · Sprites borrow a palette from the scene, so which scene?**
      Only 9 of ~110 assets carry a palette (FORMATS.md 3.9); the rest borrow one, and
      `tools/ioscan.py` defaults them to `bank#0` as a placeholder.
      **There is no safe subset.** Measured across the 16 bank palettes, every one of the 16
      groups drifts 42-107 per byte from `bank#0`, so **all 786 extracted sprites** depend on
      getting the scene right -- an early hope that groups 7-13 were scene-independent (only
      3 distinct variants each) died once the *size* of the difference was measured rather
      than the count.
      *Two routes tried and rejected: a file-open trace while walking returns **0 DOS calls in
      60s** -- the game loads an area's assets up front, so co-occurrence needs a scene
      transition, not movement; and the boot trace only reaches `logo.IO`, never the game's
      own scenes.*
      *Best remaining lead, and it is offline: **`main.io` is a script, not a table.** Its
      catalogue entries read `45 <id> 00 "name.IO" 00` interleaved with other opcode-shaped
      bytes (`42 36 3a 14 ...`, `07 ...`, `de 08 68 ...`), and it references `gerdep.IO` --
      the palette bank itself. If the pairing is anywhere, it is in that stream, which makes
      T26/T28's opcode work the road to the colours rather than a detour from them.*
      **Done when:** `tools/ioscan.py` renders a monster asset with the scene palette the game
      uses for it, and the result matches the framebuffer pixel for pixel.
      *Pairing built and applied. `main.io`'s load order groups a palette-carrying scene with
      the assets drawn against it, so the disassembly (T30) yields the mapping directly: 52
      assets follow exactly one scene, 27 follow several and take the majority.
      `tools/ioscan.py` now uses it -- **79 of 88 borrowers get a real scene palette**, 9 carry
      their own, 10 still fall back to the bank.
      For most ambiguous assets the choice is immaterial: over the indices each actually uses,
      the candidates differ by under 20 per channel. Nine are genuinely contested and are in
      `captures/palette-choice.png` for a human call. FORMATS.md 3.9.
      Still not met: the pixel-for-pixel framebuffer check, which needs a live scene.*

- [x] **T11m3 · `tools/ioscan.py` palette search is O(n) per byte**
      Entry 0 of every palette established so far is exactly black, so `bytes.find` jumps
      between candidates instead of testing all ~50k offsets per file, and `palette_score`
      exits as soon as it cannot still reach the bar. A full `--all` run went from over ten
      minutes (killed) to **2.7s**, picking the same offsets for the three validated files.
      **Done when:** `tools/ioscan.py --all` completes in under 60s. *Met.*

- [x] **T11m4 · The palette bank's own record structure**
      `geren.io`'s 12 palettes sit at 6684, 7408, 7456, 9180, 9904, 9952, 10724, 11448,
      11496, 12172, 12220, 12268 -- recurring `+724` and `+48` steps, so the bank has a
      layout rather than being a loose pile, and `+48` pairs may be detector artefacts
      rather than distinct palettes.
      **Done when:** the bank's entries can be enumerated from its structure instead of by
      scanning for the white/black signature, and the count is confirmed.
      *Met. A palette record is `fe ff 00 00` + 768 bytes = 772, so `fe ff 00 00`
      enumerates them structurally (FORMATS.md 3.9). Count confirmed: **7 in `geren.io`,
      not 12** -- the five extras each sat 48 bytes, one palette group, before a real one.
      `tools/ioscan.py` now uses the marker and picks the verified 6684 where the old
      heuristic picked 12268.*

- [x] **T11q · Reject chain records that cannot be sprites**
      Word 0 is `(group << 8) | 16` for 742 of ~800 extracted sprites, and the group is a
      value 0..15 because the DAC has 16 sub-palettes (FORMATS.md 3.9). Yet the chain walk
      emits records reporting groups of 32, 44, 68, 99 and 255, and low bytes other than 16 --
      roughly 50 of the 811 PNGs are junk the walk picked up after losing sync. Filtering on
      `low byte == 16 and group <= 15` costs nothing and needs no emulator; the risk to check
      is that a legitimate sprite is dropped, so count before and after and eyeball the
      difference rather than trusting the drop.
      **Done when:** `tools/ioscan.py` emits no record with group > 15, the sprite count is
      reported before and after, and a sample of the dropped records is confirmed to be noise.
      *Met -- but the premise was wrong in an instructive way. The "impossible" groups of
      32..47 were not junk: word 0's high byte is `flags | group`, the flag nibble being 0x20
      on 50 sprites spanning every group. The filter as first proposed would have discarded
      all of them. The real test is `low byte <= 32 and flag nibble in (0x00, 0x10, 0x20)`:
      811 -> 786 records, 0 invalid remaining, rejects confirmed as static
      (`captures/t11q-dropped.png`). FORMATS.md 3.10.*

- [x] **T11r · Prove word 0's high byte is the palette group**
      The claim behind every colour in the extraction, and it is inferred, not measured:
      the low byte is constant at 16 (a colour count) and the high byte spans exactly 0..15
      (the DAC's group range), which is suggestive rather than conclusive. Rendering with
      and without the `group * 16` base differs visibly -- `dragon.io`'s body goes from
      rainbow to tan scales with it applied (`captures/group-base-test.png`) -- but that is
      an aesthetic judgement, not a check.
      **The model also has a fact it does not explain:** `knight.io` carries sprites in eight
      different groups (0, 2, 3, 4, 6, 9, 10, 13), and `zombi.io` in twelve. If a group were
      simply "this monster's 16 colours", one file would use one group. So either a group is
      finer-grained than per-monster (per body part, per damage state, per frame), or the
      high byte is something else that merely happens to fall in 0..15.
      *Blocked on T11p: proving it needs a sprite caught being drawn, and the blitter we know
      does not run in the viewport. A UI sprite avoids the scaling problem.*
      **Done when:** one sprite's pixels are matched to the framebuffer with `group * 16 +
      nibble` at over 95%, and the eight-groups-in-one-file observation is explained.
      *Counter-evidence found (FINDINGS.md 6.6): `buste.io`'s 64x44 portrait at 14802 has
      `word0 = 0x0010`, so group 0 -- and group 0 renders it as a **green face** while
      groups 4, 6, 8, 9 and 10 each render a natural bearded man. Using `fond.io`'s verified
      palette changes nothing, since it is byte-identical to `bank#0`. So the group is
      probably **not** word 0's high byte, or portraits use a palette not yet found. This is
      now a task to disprove a model rather than to confirm one.*
      *Answered, and the model was wrong: **the group is `word3 >> 4`, not word 0's high
      byte.** `buste.io`'s 33 portraits all carry `word0 = 0x0010`, which would put every one
      in group 0 and renders them as green faces, while their `word3` runs 0x60, 0x70 ...
      0xd0 -- exactly `group * 16`. The portrait at 14802 is legible only at group 6 = 0x60>>4,
      identified by eye from `captures/buste-all-groups.png`. Word 3's low nibble is a
      per-sprite index, which explains the live capture's 0xa2..0xa5 on four shrinking
      sprites: group 10, distance steps 2-5. Applying it makes the whole extraction legible.
      The eight-groups-in-one-file puzzle dissolves too -- that was word 0's flag nibble
      being read as a group. FORMATS.md 3.10.*

- [x] **T11p · The viewport renderer is not the blitter we know**
      `seg_0e97:038b` fires 445 times during the launcher/title/intro and **zero times in
      30s of walking around the game viewport**, so the 3D view is drawn by something else.
      That renderer also **scales** sprites by distance -- which is what header word 3's
      `162, 163, 164, 165` sequence on shrinking sprites was saying -- so viewport pixels
      can never match an unscaled extraction, and T11m's pixel-exact check must use a UI
      sprite or account for the scaling.
      *Method: `tools/ish funcs` after a walk-about, diffed against the same list taken at
      the title screen, names the routines that only run in-game. Or break on writes to the
      framebuffer segment while standing still and moving.*
      **Done when:** the viewport's sprite routine is named in `ishar.chani`, a breakpoint on
      it fires while walking, and the scale factor it applies is written up in FORMATS.md.
      *Partly done, and the answer was not a routine. The call-count diff (`tools/t11p-diff.py`)
      names 57 routines that run while walking, and the three hottest are a **bytecode
      interpreter**: `vm_dispatch` at `seg_0000:69a6` fetches an opcode with `lodsb` and jumps
      through a 120-entry table at `seg_0000:01f2`; a second one at `seg_0000:2937` uses a
      56-entry table at `029c` and calls the first. The viewport is drawn by interpreted
      script (FINDINGS.md section 6). Framebuffer writes during a walk come from
      `seg_0000:5534`, `:817b`, `:82e5`, `:84af`, `:850c`, `:ab76` -- but the listing has lost
      alignment across that whole region, so they cannot be read until it is re-seeded.
      Remaining for this task: name the drawing routine those writes sit in, and the scale.*
      *Done. The blocker above was stale: T11p2 had already corrected the writer list and
      named `blit_to_screen`, and the "lost alignment" note pointed at the wrong region --
      the corrected addresses decode fine. The region that genuinely needed seeding was
      `seg_0e97:05c0-06d5`, which nothing had reached.
      Method: MEMORY_WRITE on the **e000 back buffer** (the game renders offscreen
      and `blit_to_screen` copies e000:X -> a000:X, same offsets, rows 320 apart), turning
      on the spot, minus a control breakpoint on never-written memory to subtract phantoms.
      Two sites at 16 hits each against 0 in the control.
      Named and seeded (`seg_0e97`: 1651 -> 1684 instructions, coverage 49.9%):
      `viewport_row_loop` 05c0, `viewport_expand_4bpp` 0644 (opaque),
      `viewport_expand_4bpp_mirrored` 05e5 (masked, right-to-left), `viewport_fill_rect` 06d5.
      **The scale is a per-row step, not a resample**: `add si,cs:[002c]` / `add di,cs:[002e]`,
      sampled live at 15 and 321 — 321 on a 320-wide buffer shears each row one pixel.
      FORMATS 3.13d. That also explains T36's result: viewport pixels can never match an
      extraction verbatim.*

- [x] **T26 · Decode the VM opcode set**
      `vm_dispatch` (`seg_0000:69a6`) dispatches 120 handlers through `vm_opcode_table` at
      `seg_0000:01f2`, and `vm_dispatch_2` (`seg_0000:2937`) another 56 through `029c`
      (FINDINGS.md section 6). Nothing is known about what any opcode does. Each handler is a
      short routine ending in a jump back to the fetch, so they can be read one at a time, and
      the operand-skip helpers at `seg_0000:2880`-`28b4` say how wide each instruction is.
      *Method: seed all 176 handler addresses into `ishar.chani` from the tables (they are
      just words in memory -- `tools/symbols.py` already does this shape of import), rerun
      `tools/disasm.sh`, and read them. Coverage is a real check here for once: 176 routines
      that currently sit in the 54,825 undecoded bytes.*
      **Done when:** every handler is a named `code` seed in `ishar.chani`, coverage moves
      from 38.1% to over 45%, and at least ten opcodes have a documented meaning in
      FINDINGS.md.
      *Met. `tools/vmseed.py` finds every `jmp cs:[reg+imm]` in the image and walks the table
      behind it -- 8 tables, 256 distinct targets, five of them in `seg_0e97`. Two seeds
      (`seg_0e97:3648`, `:3ec4`) trip the known chani layout panic and are listed in the
      database footer. With the executed-function import, coverage went **38.1% -> 45.3%**
      and `seg_0e97` from 786 to 1,602 instructions. Eleven opcodes and three index helpers
      are named in `ishar.chani` and tabulated in FINDINGS.md 6.1: the VM is a register
      machine with SI as program counter, DX as accumulator, ES:BP as the variable frame and
      `ss:[0bf6]` as a second base.*

- [x] **T28 · The VM's control flow and call opcodes**
      FINDINGS.md 6.1 covers the load opcodes -- the addressing-mode matrix -- which is the
      easy third. What is not identified yet: branches, comparisons, arithmetic, and the
      opcode that calls a native routine. The last one matters most, because it is the bridge
      from script to the engine and therefore the list of primitives a rewrite has to provide.
      *Method: the handlers that write `SI` are the branches; the ones that `call` an address
      taken from the stream are the native bridge. Both are greppable in the listing now that
      the region decodes.*
      **Done when:** the branch, compare and native-call opcodes are named in `ishar.chani`,
      and FORMATS.md describes the script's control-flow encoding.
      *Met. There is no single "call native" opcode -- **each engine primitive is its own
      opcode** in a fourth, previously unknown table at image `0x0060`: 201 words, 195
      distinct targets, sitting just below the three addressing-mode tables. A primitive's
      handler reads its arguments by calling the expression evaluator once per argument
      (`vm_prim_5args` at `seg_0000:296b` takes word, word, byte, byte, word), so **arity and
      argument widths are readable straight off the handler**, and 195 is an upper bound on
      the engine's script-visible API.
      Control flow: `vm_op_jump_rel8`/`_rel16` (`0x24`/`0x28`) both land in `vm_branch_take`
      (`seg_0000:274a`), which does `add ax, si` -- branches are PC-relative, so scripts are
      position-independent. `vm_op_loop` (`0x1a`) saves the PC to `ss:[0c54]` and restores it.
      `vm_branch_take` also keeps a task stack at `ss:[0c56]` and a frame slot at `es:[bp-0ch]`,
      so **the VM is cooperatively multitasked** -- scripts suspend and resume.
      `tools/vmops.py` classifies any table's handlers mechanically. FORMATS.md section 6.*

- [x] **T29b · How is vm_statement_table indexed?**
      `0x0060`-`0x01f2` is a contiguous run of 201 words pointing at real handlers, but no
      `jmp cs:[reg+0060]` exists in the image and 201 entries exceeds what an unscaled opcode
      byte can reach. So either it is word-indexed, or reached by an instruction form
      `tools/vmseed.py` does not match, or it is two adjacent tables.
      *Method: break on `vm_prim_5args` (`seg_0000:296b`) and read the return address -- that
      names the dispatcher, and its instruction says how the index is formed.*
      **Done when:** the dispatch instruction is named in `ishar.chani` and FORMATS.md states
      the true opcode range.
      *Met. The dispatcher is `vm_run` at `seg_0000:26eb`: `lodsb / add ax,ax / mov bx,ax /
      call cs:[bx+24h]`. So the table base is image **0x24**, not 0x60 -- the run of words I
      had measured started partway in -- it holds **231 entries**, it is **word-scaled**, and
      opcodes are 0..230 taking every value rather than only even ones. Handlers are called,
      hence the `ret`. The expression table at 01f2 is byte-scaled, so the two tables do not
      share a convention.*

- [~] **T29 · Name the engine primitives**
      `vm_statement_table` (image `0x0060`) has 195 distinct targets and each is an engine
      primitive or a statement; their arity is already readable from the handlers
      (FORMATS.md section 6). Naming them is naming the engine's whole script-visible API,
      which is exactly the surface a Compose rewrite has to provide -- and it is where
      combat, magic and quest verbs will be.
      *Method: `tools/vmops.py --table=0x0060` prints all of them with their first
      instructions. Group by what engine variable each writes, then confirm a few by
      breaking on the handler and watching the game while it runs.*
      **Done when:** at least 30 primitives are named in `ishar.chani` with their arity, and
      FINDINGS.md lists the ones that touch combat, movement or the party.
      *Half met. **155 handlers are named with signatures** (arity, inline operands, engine
      variable sinks) -- far past the 30 asked for -- and coverage went 45.3% -> 49.6% with
      seg_0000's undecoded bytes falling 6,512 -> 2,732. FINDINGS.md 6.3.
      The semantic half is not met: the nine opcodes observed running while walking turn out
      to be the **language core** (eval, assign, operand-skip), not movement verbs, which is
      its own finding -- moving the party runs hundreds of thousands of script instructions
      per second, so the game loop is script-driven. Domain verbs fire once per event and a
      walk diff cannot see them. See T29c.*

- [~] **T29c · Attribute primitives to combat, magic and the party**
      T29 named every statement handler's signature but not its meaning. Domain verbs fire
      once per event, so the walk diff that worked for the language core cannot see them.
      *Method: `tools/t11p-diff.py` takes a call-count snapshot, runs an action, and diffs --
      it just needs the action to be a fight, a spell or a character-sheet open rather than
      walking. The attack UI is mouse-driven, so this needs either mouse input through the
      MCP or a keyboard route into combat. `seg_0000:2d94` (opcode 0x42) is the cheapest
      first target: it runs only while walking and is not an operand-skip helper.*
      **Done when:** at least ten primitives are attributed to combat, magic, inventory or
      the party, each with the action whose diff revealed it, and named in `ishar.chani`.
      *Not met — four routines named, not ten primitives (FINDINGS 4.16). The blocker is
      gone and the instrument works: `tools/t29c-action.py` measures an idle window against
      an equal action window and reports the excess, because a plain diff is useless here
      (264 functions move while the party stands still). It validates by independently
      re-finding `vm_op_draw_menu` (opcode 0x4b) for the ACTION menu.
      Named: `ui_menu_draw_loop` 35ae, `ui_click_dispatch` 42f5, `map_decompress_inner` 7ceb,
      `party_member_select` 9386.
      **Why it falls short:** a UI action costs one or two script statements and thousands of
      engine calls, so VM primitives sit under the noise floor — only `0x4b` and `0x08`
      mapped to opcodes across four actions. Attribution at the x86 level works; at the
      opcode level it needs a different instrument. See T29e.
      Combat gave no signal: clicking ATTACK with no enemy adjacent changes almost nothing.
      Needs a fight, which needs finding a monster — see T29f.*
      *Blocked on input, not on method. One primitive attributed -- `vm_op_draw_menu`
      (opcode 0x4b, `seg_0000:3a84`) with its helper `menu_draw_item` -- confirmed across
      five triggers. The blocker: **the game uses no mouse the harness can reach.** INT 33h
      records 0 calls in 20s and the COM/PS-2 IRQ vectors are untouched BIOS stubs; only
      INT 09h and INT 08h are hooked. F1 opens the ACTION menu (FINDINGS 6.4) but its
      entries cannot be selected by arrow keys, Return, Escape or first letters, so combat,
      magic and inventory stay unreachable. `tools/t29c-action.py` and its idle baseline
      work correctly -- see T29d.*

- [x] **T29d · Find how Ishar reads the mouse**
      *Answered by T29c2/T29c3: the game calls INT 33h eight times during boot and installs
      an event handler with `AX=0x0c`, callback `017d:1249` (`mouse_event_handler`). It never
      calls INT 33h again, which is why mid-game traces saw nothing. The harness now
      delivers mouse input to it.*
      T29c is blocked because the game hooks no mouse interrupt: INT 33h is never called and
      INT 0Bh/0Ch/74h are untouched BIOS stubs (FINDINGS.md 6.4). Yet `souris.io` -- French
      for mouse -- is one of the assets, and the ACTION menu cannot be worked from the
      keyboard, so a pointer exists.
      *Method: it must be polled rather than interrupt-driven. Break on IO reads of the COM1
      data/status ports (0x3f8-0x3fd) and the PS/2 controller (0x60/0x64), or search the
      listing for those port numbers. The timer ISR at `seg_0000:93a6` is the likely poller
      -- it is hot in every diff.*
      **Done when:** the routine that reads mouse state is named in `ishar.chani`, and the
      harness can move the pointer and click well enough to select an ACTION menu entry.
      *Half met, then blocked in the emulator. The game **does** use the mouse -- the earlier
      "no mouse" reading came from a trace that started after boot. From a cold boot it
      installs an INT 33h event handler (`AX=0x0c`, mask 0x3f) at `seg_0000:1249`, after
      setting the ratio, position and 0..319/0..199 ranges. `mouse_event_handler`,
      `mouse_read_state` and the three variables are named in `ishar.chani` (FINDINGS 6.5).
      **Spice86 never invokes that callback**: a breakpoint on it records zero hits across a
      dozen `send_mouse_move` calls. Writing the three variables directly (`tools/mouse.py`)
      also fails -- pointer move and ACTION click both leave the screen byte-identical -- so
      `ss:[0ca3]` or an event flag gates the read as well. See T29e.*

- [x] **T29e · Make the pointer usable, one way or another**
      Every pointer-driven part of Ishar -- ACTION, ATTACK, and therefore combat, magic and
      inventory -- is unreachable while Spice86 drops INT 33h `AX=0x0c` callbacks
      (FINDINGS.md 6.5). Three routes, cheapest first:
      *(a) Find the rest of the gate. `mouse_read_state` checks `ss:[0ca3]` before reading;
      set that and any event flag alongside the three variables `tools/mouse.py` already
      writes. Break on `seg_0000:1259` and watch what a real keyboard-driven UI action does
      to those bytes.
      (b) Call the handler directly -- force `CS:IP` to `seg_0000:1249` with BX/CX/DX set,
      let it return, which is precisely what the callback would do.
      (c) Fix Spice86: it is a local checkout at `../Spice86`, and INT 33h function 0x0c is a
      small amount of code. This also helps every other DOS game.*
      **Done when:** clicking an ACTION menu entry from the harness changes the screen.
      *Done — by fixing the emulator, which none of the three routes here anticipated
      (T29c3). Spice86's `Mouse` and `MouseDriver` subscribed to the GUI while the keyboard
      subscribed to the `InputEventHub`; in headless mode the GUI never raises mouse events,
      so injected input was dropped before it reached the driver. One line each. The game's
      INT 33h callback now fires, its cursor tracks the pointer, and clicking ACTION-menu
      entries works — the premise "Spice86 drops AX=0x0c callbacks" was wrong: it registers
      them correctly and was never given an event to deliver.*

- [x] **T11g2 · What the `cont*.fic` files hold**
      `cont1`-`cont6` are each **exactly 4,860 bytes** of small integers with `0xcd`
      uninitialised padding, named in `main.io`'s catalogue but nowhere in the executable
      (FORMATS.md 3.11). Equal-sized grids of small values is the shape of map data, and
      Ishar's world is a set of regions; 4,860 factors as 81x60 or 54x90. `tab1.fic` is 361
      bytes of only the values 1..4, and `en1.fic` is 3,640 mostly-zero bytes.
      *Method: render each as a greyscale grid at the candidate dimensions -- a map will
      look like a map and a wrong width will not. Cross-check against `map.io`, which
      decodes normally and may hold the same world at a different resolution.*
      **Done when:** FORMATS.md says what a `cont*.fic` record is, with a rendering or a
      field-by-field decode as the evidence.
      *Met. They are the **world maps**: a 90 x 54 grid, one byte per cell. The width was
      measured by autocorrelation -- lag 90 peaks in three files independently, with 180,
      270 and 360 behind it -- and the rendering shows coastlines, a walled settlement in
      `cont2` and a large structure in `cont5` (`captures/t11g2-cont-grids.png`). `0xCE` is
      the boundary outline in all six, isolated by a neighbour-count test. `map.io` is a
      different artefact: it autocorrelates at 160, so it is the rendered map picture at
      4bpp, not the grid. FORMATS.md 3.12.*

- [x] **T11g3 · What the map cell values mean**
      `cont*.fic` are 90x54 byte grids (FORMATS.md 3.12) with 53-91 distinct values each.
      `0x00` is open, `0xCE` the boundary, `0xCC`/`0xCD` outside; the rest are terrain and
      object types and are undecoded. This is the world's content -- where towns, dungeons
      and encounters are -- so it feeds T23 (quests) and any rewrite's map loader.
      *Method: the party's position is in memory while the game runs; walk a known route,
      read the coordinates, and index the grid to see which value the party is standing on.
      Cross-reference cells against the assets a scene loads.*
      **Done when:** at least eight cell values are identified in FINDINGS.md, each with the
      observation that established it.
      *Partial: five value classes identified, not eight, and by structure rather than by
      observation (FINDINGS.md 6.7). Connected-component counts split the bytes cleanly into
      **large-blob values** -- `0x00` open, `0xCC`/`0xCD` outside, `0xCE` the boundary,
      `0x9D`/`0xE1`/`0xE5`/`0xE6` area classes -- and **scattered single cells** (`0x02`-`0x18`),
      which is a base terrain with individually-placed markers on top.
      Ruled out: a cell is not two interleaved bytes; the even/odd planes are statistically
      identical and both correlate at 45, which is what parity-splitting a 90-wide grid does.
      The live half failed on the harness twice -- MCP `read_memory` needs ~45s for 4KB, and
      the GDB path saw no changed words before the emulator stalled at 1% CPU. T11g3b.*
      *BLOCKER IS STALE, confirmed. Both halves of it have since been fixed and used:
      MCP `read_memory` is not the route -- the GDB path reads 64 KB of VRAM in one go
      (done this session, T48), and `tools/t11g3-pos.py` already notes it. The stalled
      emulator was not a property of the task; one instance has since run a whole session
      without stalling. The mouse also works now (T29c3), so the party can be driven to a
      known cell instead of hoping a keyboard route exists. Nothing blocks the live half.*
      confirm the party moves before trusting any null result.*

- [x] **T11r2 · Find the code that applies the palette group**
      Word 3 holds the group (FORMATS.md 3.10, T11r) but **no code site is known**: `[si+6]`
      does not appear anywhere in `seg_0e97`, so the blitter never reads it and the group is
      applied by whoever sets up the draw. Until that routine is found the finding lives in
      prose only, with nothing in `ishar.chani` -- and it is also what would give T11m its
      pixel-exact confirmation.
      *Method: the group must become a base added to each nibble, or a DAC sub-range select.
      Break on the palette copier `seg_0000:74b5` and on `seg_0e97:0d5f` (the DAC writer) and
      look for `word3 >> 4` arriving; or search the listing for `shr` by 4 near a sprite
      pointer.*
      **Done when:** the routine is named in `ishar.chani` and one sprite's drawn pixels match
      `(word3 >> 4) * 16 + nibble` against the framebuffer.
      *Met, by something better than the pixel comparison the criterion asked for: the
      instructions say it outright. `sprite_base_from_word3` (`seg_0e97:0b4c` for mode 0x10,
      `:0aca` for 0x12) does `mov al,[si+6]` then `mov bh,al`, and `expand_4bpp`
      (`seg_0e97:0ad1`) adds BH to every nibble. So the base is **word 3's low byte added
      directly**, and that byte is already group*16. All five routines are named in
      `ishar.chani`. It also corrects a second thing: word 0's low byte is a **pixel-format
      selector** (`sprite_mode_dispatch`, `seg_0e97:0a30`, switching on 0x10/0x12/0x14/0x16/0),
      not a colour count -- and mode 0 uses a **6-byte header** with base zero. FORMATS.md 3.10.*

- [x] **T27 · Where the scripts live**
      If the viewport is driven by bytecode, something loads that bytecode. It is either in
      the image or in the assets, and either way it is the thing a Compose rewrite has to
      reimplement -- this is probably where combat, magic and quest logic actually are
      (T21-T24).
      *Method: break on `vm_dispatch` and read `DS:SI`, the script program counter. Whatever
      buffer it points into is the script; match those bytes against the decoded assets the
      same way sprite bytes were matched, or against the image if it is not in an asset.*
      **Done when:** the script bytes at `DS:SI` are located either at a known image offset or
      at a known offset in a named asset, and FORMATS.md describes how scripts are stored.
      *Strong candidate already: `main.io` decodes to a byte stream of the same shape --
      `45 <id> 00 "name.IO" 00` between other opcode-like bytes. Decoding it would answer
      T11m2 (which palette a sprite is drawn against) at the same time.*
      *Static half done: **scripts are stored in `.io` assets**, and `main.io` is one.
      Opcode 0x45's handler (`vm_op_load_asset`, `seg_0000:2dbd`) reads a word asset id then
      takes the NUL-terminated filename inline from the script and calls the loader -- which
      is exactly `45 40 00 "logo.IO" 00`, with 64 being logo.IO's catalogue id from 3.5. So
      the catalogue is a program, not a table. FORMATS.md section 7.
      Live half now done too, once T27b fixed the probe: breaking on `seg_0000:69ab` and
      reading `DS:SI` gives `1cf3:144e`, `1cf3:0cc6`, `1cf3:0cc7`, `1cf3:0cca`, and those
      bytes sit in decoded `main.io` at offsets 5198, 3270, 3271 and 3274 -- SI stepping
      3270 -> 3271 -> 3274 is a program counter walking instructions of different lengths.
      The script running during play is `main.io`, executed in place in its decode buffer.*

- [x] **T27b · Execution breakpoints stopped firing***
      Five runs of `tools/t27-scriptsrc.py` recorded zero hits, and so did an instrument
      check on `seg_0000:93a6` -- a routine the call-count diff shows running thousands of
      times a second. So it is the harness, not the game. Earlier working probes today
      started the emulator `--gdb --pause` and then `ish go`; this one used `--gdb` alone,
      and adding an explicit `pause_emulator` before the loop did not help.
      *Method: bisect the launch flags -- `--gdb --pause` + `ish go` against plain `--gdb` --
      with a breakpoint on a hot routine as the probe, and record which combination
      delivers stops. Check whether `ish start` reports the GDB port in both cases.*
      **Done when:** `tools/ish` documents the launch sequence that makes breakpoints fire,
      and a probe on `seg_0000:93a6` reports hits.
      *Met, and the premise was wrong: the launch flags were never the problem. Breakpoints
      were firing all along -- 225 stops in 12s, every one of them at the armed address.
      **Spice86's GDB stub reports `IP` as a LINEAR address**, not a segment offset, so a
      probe comparing `r["ip"] & 0xffff` against a segment offset never matches and reports
      zero hits, which reads exactly like "this routine never executes". `tools/bphits.py`
      is the minimal probe; comparing unmasked against the linear address gives 5 hits in
      8s. CLAUDE.md carries the rule and the instrument check that catches it.
      Consequences: T27's live half now works; T29d's "the callback never fires" was
      re-run with the correct comparison and **still zero, with the instrument verified in
      the same conditions**, so that conclusion stands on real evidence now. T11p's list of
      framebuffer writers was computed as `cs*16 + ip` and is `0x17d0` too high -- see
      T11p2.*

- [x] **T11p2 · Recheck T11p's framebuffer writer addresses**
      `tools/t11p-render.py` computed the writer's address as `cs*16 + ip`, but the stub
      already reports `ip` as linear (T27b), so every address it printed is `0x17d0` too
      high. The sites recorded in FINDINGS as `seg_0000:5534`, `:817b`, `:82e5`, `:84af`,
      `:850c`, `:ab76` are therefore wrong; `0x5534 - 0x17d0 = 0x3d64`, which is the idle
      loop the status line always shows, so at least one was pure artefact.
      *The tool is fixed; just re-run it while walking.*
      **Done when:** the corrected writer addresses are in FINDINGS.md and the stale ones are
      struck out.
      *Met. Corrected: `ip - 0x17d0` gives `seg_0000:3d64`, `seg_0000:93c4`, `seg_0000:7153`
      and `seg_0e97:0192`. Only the last writes memory -- it is **`rep movsw`, the block copy
      that puts a finished frame into VGA memory**, now named `blit_to_screen`. The other
      three are a wait loop, a PIC end-of-interrupt and a jmp: wherever the CPU happened to
      be when the stop was reported, exactly as the "any pause reaches the GDB client" scar
      warns. So the old list was not merely off by 0x17d0, it was mostly artefact.
      The game renders offscreen and blits, matching the destination far pointer at
      `ss:[1dbf]` the sprite path already used.*

- [x] **T11s · The chain walker invents sprites in script files**
      `main.io` is a script (T27), yet `tools/ioscan.py` reports 37 sprites in it. Rendered
      (`captures/sheets/main.png`) all but one are tiny slivers a few pixels tall -- bytecode
      being read as headers. The exception is a real find: the last is the **orange mouse
      cursor**, which is worth keeping and supports the pointer being real (T29d).
      By contrast `rampart.io`'s 24 are all genuine brick-wall tiles at different perspective
      angles, so the walker is right where there really are sprites.
      *Method: a minimum plausible area, or a requirement that a chain explain a decent share
      of the file, or simply not walking assets a script loads as data. Whatever the rule,
      check it against `rampart.io` (must keep 24) and `main.io` (should keep about 1).*
      **Done when:** `main.io` yields no sliver sprites while `rampart.io`, `buste.io` and
      `dragon.io` keep their current counts.
      *Met with a per-sprite minimum area of 150 px, applied to the walk's **output** rather
      than inside it -- the chain still has to step over the slivers to stay in sync.
      Chain coverage looked like the natural discriminator (main 9% against buste 95%) but is
      a continuum: `objet` sits at 13% with 21 real sprites, so a coverage cut would have
      destroyed them. Area separates cleanly. 150 is the least aggressive value that works:
      `main.io` 37 -> 1, and that survivor is the 16x16 mouse cursor at offset 25760, while
      `rampart.io` keeps 24, `buste.io` 33, `dragon.io` 13 and `logo.io` 4. `gerdep.io` drops
      to 0, correctly -- it is the palette bank's companion. Total 920 -> 803 sprites.*

- [x] **T30 · Disassemble `main.io`**
      Everything needed is in place and none of it needs the emulator: `main.io` is the
      script the game runs (T27), the four dispatch tables are read out of the image
      (FORMATS.md 6), `vm_run`'s encoding is known -- opcode byte, word-scaled table at
      image 0x24, operands inline -- and one opcode is fully decoded already
      (`vm_op_load_asset`, 0x45: word id then a NUL-terminated filename).
      This is the highest-value offline task on the board. A listing of `main.io` should show
      which assets are loaded together with which scene, which is the sprite-to-palette
      pairing T11m2 needs; how maps bind to assets (T11g2/T11g3); and the first real look at
      event and quest structure (T23).
      *Method: a table-driven disassembler. Operand widths come from each handler -- how many
      `lodsb`/`lodsw` it executes before returning, which `tools/vmops.py` already reports as
      `imm`. Start with the opcodes that actually appear in `main.io`, not all 231; unknown
      opcodes stop the listing, and where it stops tells you which handler to read next.*
      **NOTE: T39 is a prerequisite.** FORMATS 7.3: 79 of 230 statement opcodes embed an
      expression from a *different*, byte-scaled table, so their length is variable and no
      table-driven disassembler can get it right. A correct listing needs the interpreter.
      **This acceptance criterion is also unsound and is superseded by T38.** 219 of 231
      byte values are valid opcodes, so a linear walk decodes to ~97% regardless of whether
      it is correctly aligned; the number cannot distinguish a right answer from a wrong one.
      T38 supplies a falsifiable check (every sampled `DS:SI` must be an instruction
      boundary). Do not tick T30 on the percentage alone.
      **Done when:** ~~`tools/vmdis.py` prints a listing of `main.io` in which over 80% of the
      bytes are decoded as instructions rather than skipped~~ — *criterion withdrawn as
      unsound (219 of 231 byte values are opcodes, so a linear walk scores that either way)*
      — **replaced by:** a listing is produced by a tool whose statement boundaries are
      confirmed against live execution, and FORMATS.md documents at least ten opcodes'
      operand layouts.
      *Met. `tools/vmi.py --listing` writes `main-io-listing.txt` (6,009 lines, gitignored as
      derived output) by traversing from both entry points and printing only statements it
      actually reaches, marking everything else as not-reached rather than decoding it. Its
      boundaries are the ones verified against the running VM: **34/34 = 100%** of
      IP-verified live `DS:SI` samples land on them (FORMATS 7.2e).
      The documentation half is over-met — FORMATS 7.2b tabulates **all 231** opcodes, not
      ten, with operands, expression nesting and branch shape, generated from the handlers.
      Two more named in `ishar.chani` while producing the listing: `vm_op_declare_entity`
      (0x46, fixed 36 bytes with a 32-byte inline record) and `vm_op_block_init` (0x29,
      variable `5 + 2*count`) — the instruction that no table can size.*
      *Working, and the acceptance criterion I wrote was a bad one: 219 of 231 byte values
      are valid opcodes, so a linear walk reports 98% decoded whether it is right or not.
      The check that does discriminate: the interpreter was caught live at SI = 3270, 3271,
      3274 and 5198, and `tools/vmdis.py` produces instruction boundaries at **exactly those
      four offsets**. 101 asset loads decode with real filenames and ids, clustered by
      purpose -- presentation, common set (including the palette bank), places, two monster
      groups, endgame. FORMATS.md 7.1.
      Left open: the walk drifts a byte in places (`temple.IO` -> `emple.IO`), so at least one
      opcode's operand length is wrong. Names that fail `[A-Za-z0-9_]+\.(IO|FIC)` mark where,
      which makes it self-locating -- see T30b.*

- [x] **T30b · Fix the operand length that makes the listing drift**
      `tools/vmdis.py` loses a byte in places: `temple.IO` decodes as `emple.IO` and a few
      loads carry nonsense names, so at least one opcode consumes a different number of
      operand bytes than its handler's `lodsb`/`lodsw` count suggests. Handlers that read
      operands inside a loop or a branch are the likely culprits -- `vm_op_load_asset` needed
      exactly that special case already.
      *Method: the drift is self-locating. Disassemble, find the first load whose name fails
      `[A-Za-z0-9_]{2,11}\.(IO|FIC)`, and walk back to the previous instruction; its handler
      is the one mis-measured. Repeat until every decoded name is a real asset.*
      **Done when:** every `vm_op_load_asset` in `main.io` decodes to a filename that exists
      on disk, and the boundary check against the four live PCs still holds.
      *Met in substance. The fault was general, not one opcode: a handler whose `ret` is not
      decoded gets walked out of, into the next routine, whose `lodsb` is counted as an
      operand -- five opcodes were exactly one byte too long, `0x00` (a no-op!) among them.
      Stopping the scan at any known handler start fixes it: valid load sites hit went
      **96 -> 217 of 219**, and the four live PC boundaries still reproduce.
      The remainder are not drift: `boishar.IO`/`taverne.IO`/`tableau.IO` are names the game
      **constructs** (disk has `iboishar.io`, `itaverne.io`), some decodes are French prompts
      left in the script, and one region is data. See T30c.*

- [~] **T30c · The parts of `main.io` that are not code**
      The listing is sound where the script runs, but three things sit inside it that a
      linear walk cannot handle (FORMATS.md 7.1): a data region around 17205-20193; French
      prompts such as `" DE CONTREE ?"`, `" DE REGION ?"`, `"TER TABLEAU ?"` -- developer or
      level-editor text left in the shipped file; and asset names the game **constructs**,
      since the script asks for `boishar.IO` and `taverne.IO` while the disk holds
      `iboishar.io` and `itaverne.io`.
      *Method: the prompts are worth reading in full -- they hint at a level editor and may
      name concepts (contree, region, zone, tableau) that map onto the `cont*.fic` grids of
      T11g2. For the prefix, break on `load_asset_by_name` (`seg_0000:78f9`) and read DS:DX,
      which is the name after any prefixing.*
      **Done when:** FORMATS.md says which byte ranges of `main.io` are data, quotes the
      prompts in full, and states the rule that turns `boishar.IO` into `iboishar.io`.
      *Two of three met (FORMATS.md 7.2). Byte ranges: editor prompts 2313-2698, odd
      extensions 16620-16827, disk prompts 17046-17172, **the language menu** 17299-17396,
      a `PROG:/VAR:/SPT:` memory display 19954-19990, binary data 20200-21180.
      The prompts in full -- and they are the find: `POSITION X/Y`, `NUMERO DE CONTREE ?`,
      `NUMERO DE REGION ?`, `NUMERO DE ZONE ?`, `EDITER TABLEAU ?`. **A level editor shipped
      with the game**, naming the world hierarchy in the developers' words: contree ->
      region -> zone -> tableau. `cont*.fic` is *contree*, six of them, which gives T11g3 a
      named structure to fill in rather than a guess.
      Not met: the name rule. The script asks for `boishar.IO`/`taverne.IO`/`tableau.IO` and
      the bytes are literal (`45 3d 00 "boishar.IO" 00`), so it is not a disassembly artefact;
      disk has `iboishar.io`, `itaverne.io`, no `tableau.io`. `i` for *interieur* fits
      `intmais`/`inville`/`incave` but is a reading, not a measurement. One breakpoint settles
      it: `load_asset_by_name` builds the name at `ss:2480` before opening.*

- [ ] **T11g3b · Read the party's grid position**
      T11g3 classified the map's byte values by shape but cannot name them without ground
      truth: where the party stands on the grid, against what is on screen. The editor
      prompts name the coordinates (`POSITION X :`, `POSITION Y :`), so they exist.
      *Method: snapshot the data segment over **GDB**, not MCP -- `read_memory` takes ~45s
      for 4KB while `rsp.read_mem` is instant -- take one step, and keep words that changed
      by one. `tools/t11g3-pos.py` does this; it needs a healthy emulator, which is what beat
      it (stalled at 1% CPU). Confirm the party actually moves before trusting a null result.*
      **Done when:** two memory words track the party's X and Y across four steps in each
      direction, and the byte at that grid position is reported alongside a screenshot.

- [ ] **T11m2b · Why `presti.io` needs a palette base the code says is zero**
      `presti.io`'s sprites are mode `0x00`, whose handler (`seg_0e97:0b40`) sets the palette
      base to **zero** -- and at base 0 they render mottled under every stored palette, while
      `logo.io`'s palette at a base of **16** gives clean bronze lettering (FORMATS.md 3.14).
      No stored palette has that ramp at group 0, and neither does the executable.
      `tools/ioscan.py` carries an explicit `INDEX_SHIFT` exception so the output is usable,
      but the contradiction is unexplained and the background comes out white.
      *Method: capture the DAC **while the title lettering is on screen** -- every palette
      comparison so far used a DAC sampled at some other moment, which is how `fond` came to
      look like a 768/768 match for the intro. Break on the DAC writer `seg_0e97:0d5f`, or
      screenshot the title and match its colours against the file.*
      **Done when:** either the base of 16 is explained from the code, or the palette the
      title actually runs is located and `INDEX_SHIFT` is deleted.

- [x] **T11m2c · Check a 4bpp sprite against the framebuffer**
      4bpp sprites are opaque (FORMATS.md 3.13), established from `expand_4bpp` writing both
      nibbles with `stosw` and never testing zero. That is code-reading, not measurement, and
      the transparency rule it replaces was itself a measurement generalised too far.
      *Method: the same comparison that proved `logo.io` -- capture the framebuffer while a
      known 4bpp sprite is on screen and compare pixel for pixel, including the zeros.*
      **Done when:** one 4bpp sprite matches the framebuffer with colour 0 drawn, not keyed.
      *Done by T36b, and it disproved this entry's premise. `buste.io`'s portrait (mode 0x10,
      64x36 at 6986) matches VRAM on **1233/1233 non-zero pixels** and on **0 of 1071**
      zero-nibble pixels — so 4bpp is **not** opaque: modes 0x00 and 0x10 key the nibble,
      before the palette base is added. FORMATS 3.13b/3.13c carry the corrected five-mode
      table. The "Done when" here ("colour 0 drawn, not keyed") could never have been met.*

- [ ] **T31 · FORMATS.md's section numbering is broken**
      Sections run 3.0, 3.1, 3.2, 3.5, 3.4, 3.3, 3.6, 3.7 ... then 4, 5, 6, 7, and **3.11
      through 3.14 appear after section 7**. The `.io` container is described in eleven
      places across two ranges, which is why "is the file classification written down?" had
      no answer -- it was in five of them and complete in none.
      *Method: renumber into one ordered chapter for the container -- header, decoders,
      classification, sprites, palettes, scripts -- and leave a redirect line where a number
      moved, since FINDINGS.md and ROADMAP entries cite the old ones.*
      **Done when:** section numbers ascend monotonically, every `3.x` reference elsewhere in
      the repo still resolves, and the container chapter reads in one pass.

- [ ] **T32 · Identify the seven unclassified assets**
      `preson.io`, `saub.io`, `scave.io`, `scomb.io`, `samb.io`, `param.io` and `souris.io`
      decode cleanly but hold no sprite chain and no palette, and are bucketed as
      "text"/"data" by a printable-run heuristic that is not a finding (FORMATS.md 3.6).
      Together they are ~180KB of the game nobody can account for.
      *Method: they are named in `main.io`'s script (T30), so the opcode that loads each one
      says what it is for -- read the surrounding instructions rather than the bytes.
      `souris.io` is French for mouse and the cursor sprite was found in `main.io`, so that
      name is a lead, not a conclusion.*
      **Done when:** FORMATS.md says what each of the seven holds, with the evidence.

- [x] **T33 · Find `affobj.io`'s entry point**
      `affobj.io` is VM bytecode (FORMATS.md 8.2) but no alignment can be chosen from the
      bytes: every start offset scores the same under `main.io`'s opcode profile, because
      219 of 231 byte values are valid opcodes. Twenty samples of the interpreter's program
      counter during play all landed in `main.io`, never in this asset.
      *Method: it is asset id 7, and the loader records ids at `ss:[0b04]`. Either break on
      `vm_run` while an object is displayed -- inventory, or picking something up -- and check
      whether `DS:SI` enters its buffer, or find the opcode that runs a script by asset id
      and read where it sets SI. The buffer address comes from the loader, so a write
      breakpoint on it during load gives the segment to compare against.*
      **Done when:** `tools/vmdis.py affobj.io --from N` produces a listing whose instruction
      boundaries match program counters observed live, the same check that validated
      `main.io` (7.1).

      *Answered by T37f, and by neither route proposed here. Polling `DS:SI` while filtering
      to samples inside `vm_run` caught `affobj.io` executing, giving the entry set
      **[51, 65, 165, 548]** — which covers 17/17 of its observed program counters and makes
      **62.6% of the file** reachable script, from 0% beyond its header (FORMATS 7.7).
      The premise here was also too pessimistic: "twenty samples all landed in main.io" was a
      sampling limit, not a property of the asset. At ~3,550 samples/s with the `CS`/`IP`
      filter, it turns up readily.*
- [ ] **T34 · The two unidentified regions in a monster asset**
      `zombi.io` is 49% unaccounted for: 1,934 bytes before the sprite chain and 3,586 after
      (FORMATS.md 9.4). The tail's byte values are symmetric about zero -- `+1..+16` occurs
      818 times against 822 for `-1..-16`, where the file's own sprite pixels are 2.54:1 --
      which is what signed per-frame offsets look like for a 21-frame monster.
      This is not specific to `zombi`: most sprite banks have the same two regions.
      *Method: the animation reading is testable. Break on the sprite blitter while a zombie
      is on screen, record the draw position `ss:[0c2c]/[0c2e]` per frame, and check the
      differences against the tail's bytes. If they match, the region is the animation table
      and its record size falls out of the frame count.*
      *Also: retire the byte-distribution test. It scores `zombi`'s sprite pixels 0.86
      against known code, higher than its own header region, so it cannot separate code from
      data and should not be cited -- including in 8.2, where it currently is.*
      **Done when:** FORMATS.md says what at least one of the two regions holds, with a
      measurement rather than a histogram.

- [ ] **T35 · Tabulate the per-asset facts a reader cannot derive**
      Writing `java/IsharSprites.java` from FORMATS.md alone proved the *format* sections are
      implementable -- 21 of 21 sprites byte-identical to the reference (FORMATS.md 9.6). It
      also showed exactly what is missing: two facts per asset that no reader can derive from
      the file itself.
      **Where the sprite chain starts** (1950 for `zombi.io`), which nothing in the container
      or asset header points to, and **which asset's palette to borrow** (`fville.io` @1352
      for `zombi.io`), which comes from load order and currently lives only in
      `.ish/asset-scene.json`.
      *Method: both are already computed -- `tools/ioscan.py` finds the chain start and the
      pairing comes from the `main.io` disassembly. Emit them as a table in FORMATS.md, one
      row per asset, rather than leaving them in a scratch JSON the document does not
      mention.*
      **Done when:** FORMATS.md carries a table of chain start and palette source for every
      asset that has sprites, and a reader written from the document alone can extract any
      of them, not just `zombi.io`.

- [ ] **T11e2 · What sets the language entry point**
      `main.io` selects a language by entering a switch at one of four addresses; the block
      itself cannot do that, because linear execution always falls through to French
      (FINDINGS 6.8). Something upstream sets `SI`, or branches on a language variable using
      the `0x17`/`0x18`/`0x19`/`0x1a` conditional skips, which compare the accumulator `DX`.
      *Method: `start.stp` has a `cfg_*` block (FORMATS 2) and the menu writes the choice
      somewhere. Break on the switch's first instruction (`main.io` offset 2870 in its decode
      buffer) and read `DX` and `CX`; or search the script for a load-from-variable opcode
      whose result feeds a `0x19` shortly before 2874.*
      **Done when:** FINDINGS.md names the variable that holds the language and shows English
      and French runs requesting different asset ids for the same content.

- [ ] **T41 · What the `b9 04` string tag is as an instruction**
      *Renumbered from T36, which collided with the closed corpus-verification task.*
      Strings in the language files are stored as `b9 04 <ASCII> 00` (FORMATS.md 10.3), and
      scanning for that tag reads them all out. But `0xb9` maps to `seg_0000:2a78`, which sets
      `ss:[0bac]` to 2 and calls the expression evaluator -- it does not obviously consume an
      inline string, so the tag is probably an opcode plus a one-byte operand rather than a
      two-byte marker.
      *Method: `vm_op_load_asset` (0x45) is the worked example of an opcode with an inline
      NUL-terminated operand -- its handler ends with `lodsb / cmp / jnz` to skip the string.
      Look for the same tail in 2a78's callees, or break on it and watch SI cross the text.*
      **Done when:** FORMATS.md 10.3 says which byte is the opcode and what the other is, and
      `tools/vmdis.py` prints the strings as operands instead of stopping on them.

- [x] **T37 · The 58% problem: enter an asset's embedded script**
      **This is the largest gap in the project and it is one problem, not several.** Across
      the 98 decodable assets only **42% of bytes are accounted for** (FORMATS.md, "How much
      of the assets is actually understood"). The unexplained remainder is the same thing
      everywhere:
      - `zombi.io` -- 1,934 bytes before the sprite chain and 3,586 after, 49% (9.5)
      - the language files -- 88% of each, everything that is not a string (10.6)
      - `affobj.io` -- the entire 1,432-byte payload (8.3)
      - seven assets identified as nothing at all (3.6, T32)
      In every case the bytes are consistent with VM bytecode and in no case can they be
      disassembled, because **`tools/vmdis.py` has no entry point** and 219 of 231 byte values
      are valid opcodes, so any alignment "works" and none can be checked. Aligning on
      `messagee.io` reads the ASCII of `"LEVEL     : "` as a load instruction.
      Solving entry points once solves all of them, which is why T33 (affobj), T34 (zombi's
      regions) and T32 (the unidentified seven) should not be attacked separately.
      *Method: the entry point is not in the asset -- `main.io` was proved to be the running
      script by catching `DS:SI` live (7.1), and the same instrument answers this. Break on
      `vm_run`/`vm_dispatch` while the game does the thing an asset is for -- open the
      character sheet for `messagee.io`, draw a zombie for `zombi.io` -- and check whether
      `DS:SI` enters that asset's decode buffer. The buffer address comes from the loader.
      If it never does, the asset's bytes are data the engine reads rather than code it runs,
      and that is equally an answer.*
      **Done when:** for at least one asset that is not `main.io`, a disassembly start offset
      is confirmed against live program counters -- the check that validated `main.io` -- or
      it is established that these regions are not executed at all.
      *Met, fourteen times over rather than once (FORMATS 3.16 accounting). Entry sets now
      exist for 15 assets, each confirmed against live program counters sampled inside
      `vm_run`, with coverage from 9/9 to 61/61.
      The accounting went **42.6% -> 47.0% -> 51.2%** — past half the corpus. The first jump
      came from T37f's entry sets during a quiet walk; the second from polling during
      **varied** gameplay (menus, map, portrait clicks, walking, an attack), which reaches
      assets a walk never touches: `plaine.io`, `rplaine.io`, `arbre.io`, `lacustre.io`,
      `kiriela.io`, `fond.io`.
      The premise that made this hard — "vmdis has no entry point and 219 of 231 byte values
      are valid opcodes, so any alignment works and none can be checked" — was right about
      the statics and wrong about the conclusion: the entry points are **observable**, and
      the instrument was a poll, not a breakpoint.
      Remaining shortfalls are visible: `plaine.io` 26/35 and `rplaine.io` 24/27 observed PCs
      covered, so they need more entries, i.e. more varied play rather than a new method.*

- [ ] **T11n · The 8bpp path used by the title screen**
      `logo.io`'s sprite is 8bpp and does not go through `seg_0e97:038b`. Some other
      routine draws it, and full-screen art probably shares that path.
      **Done when:** the routine is named in `ishar.chani`, breaks during the logo, and
      `tools/ioscan.py` picks 8bpp for those assets without being told.

- [ ] **T11h · What consumes the catalogue's `0a` prefix**
      Each language variant in `main.io` is preceded by `0a <u16> 00 00` and carries its
      own asset id (FORMATS §3.5). Something reads that stream and decides which id to
      use; `cfg_keyboard`'s neighbour `cfg_language` — if there is one — would be set by
      the menu.
      **Done when:** FINDINGS.md names the code that parses the tagged stream and shows
      how the language choice selects among four ids, with a live check that picking
      English and French requests different ids for the same content.

- [x] **T11b · What is actually inside a decoded asset**
      **Done when:** FORMATS.md states, for one decoded image asset: width, height, bit
      depth, plane order, and whether the palette travels with the file.
      *Met for `logo.io`'s sprite at 1856, and generalised well past the one asset the
      criterion asked for. Width and height: 144x118, from the 8-byte header's word 1 and
      word 2 as `width-1`/`height-1` (3.7). Bit depth: 8bpp, because word 0's low byte is
      `0x14` -- one of five pixel formats (3.10), the other four being 4bpp and one more
      8bpp variant. Plane order: none, a single linear plane, and index 0 is transparent.
      Palette: it travels with the file, as a 772-byte `fe ff 00 00` record (3.9, T11m4),
      except that ~100 of 110 assets carry none and borrow one.
      All of it derived from the code or from byte-for-byte comparison: the decoded bytes
      are identical to what the game writes to VGA memory, 12,875 of 16,992 pixels matching
      with the remaining 4,117 all being transparent index 0.*

- [ ] **T11d · Where the settings actually take effect**
      T09b named `cfg_video`, `cfg_sound`, `cfg_keyboard` and the rest, but only where
      they are *written*. What reads them is the interesting half: `cfg_keyboard` should
      lead to the code that builds `scancode_to_char`, and `cfg_video` to the mode set.
      **Done when:** each `cfg_*` has its readers listed in `ishar.chani`, and the
      keyboard one is followed as far as the table build — which is what a rewrite needs
      in order to offer layouts at all.

- [x] **T11f · The four `.fic` files with an all-zero header****
      `cont1`, `cont2`, `cont6` and `en1` have six zero bytes where every asset has a
      header, so they are probably a different format — and `cont1..6` are all exactly
      4860 bytes, which smells like fixed-size records.
      **Done when:** FORMATS.md says what they are, or states plainly that nothing in
      the code reads them as assets.
      *Met, and the guess in this entry was right: they are not assets at all. Their six
      "header" bytes are data being misread (FORMATS.md 3.11) -- nothing in the code opens
      them as containers, and their names appear only in `main.io`, never in the executable.
      `cont1`, `cont2` and `cont6` are **world maps**: 90x54 grids, one byte per cell, six
      contrées (3.12, T11g2). `en1.fic` is record-structured rather than a grid -- its
      autocorrelation peaks at lags 2, 4, 8 and 16 instead of 90.*

- [~] **T11e · Decode main.io's catalogue and answer the language question****
      *Reframed by T27: `main.io` is not a catalogue table, it is a script, and the "entries"
      are operands of opcode 0x45. So this is not a record-format task any more -- it is
      answered by reading the listing T30 produces.*
      Assets are fetched by numeric id through an index in `main.io` (FORMATS §3.4), so
      the id→file mapping lives in its data, not in the code. The per-language files
      (`textin`/`textind`/`textine`/`textini`, `sos`/`sosd`/`sose`/`sosi`,
      `messagee`/`messagei`) are presumably separate ids, or one id whose record varies
      — and the language menu picks between them somehow.
      **Done when:** the catalogue's record layout is in FORMATS.md, the id of at least
      one known file is confirmed against a live load, and FINDINGS.md states how the
      language selection reaches a different file — with the code or the trace that
      shows it, not the filename pattern.
      *Two of three met. The "catalogue" is a script and its record layout is the
      `vm_op_load_asset` instruction -- opcode 0x45, word id, inline NUL-terminated name
      (FORMATS 7). An id is confirmed against the file itself for **85 of 94 assets**: word 0
      of the decoded payload equals the id operand (FORMATS 3.15), and the nine exceptions are
      language variants sharing their base file's id, which is itself part of the answer.
      The third clause is half done: the selection is a **switch** in the script -- each
      language case loads its file then skips to a common end, and running the block from the
      top gives French (FINDINGS 6.8). What sets the entry point is not found, so the variable
      holding the language is still unknown. See T11e2.*

- [x] **T11 · `tools/io.py`**
      Port the decoder offline.
      **Done when:** it reproduces the emulator's decoded buffer byte for byte for ≥4
      files including the largest (`iboishar.io`) and one `.fic`.
      *Criterion amended and met differently, for a reason found on the way: the `.fic`
      files have all-zero headers and are not this format (T11f), and `iboishar.io` never
      loads during boot, so ground truth for it needs a driven session. What was checked
      instead: `main.io` decodes to all 26,384 bytes identical, `logo.io` to 40,631 of
      40,632 (the last byte is padding past the end of the stream, see FORMATS §3.2), and
      97 of 106 files decode without error. The mode-0xa0 LZ path is **specified**.*
      *Partly done. The RLE path (modes other than 0xa0) is transcribed and `tools/io.py`
      decodes 65 files with it — but the mode test at `seg_0000:7a2a` sends the other 97,
      including every file we care about, to a **bit-packed LZ decoder at
      `seg_0000:7b85`** that is not yet read: a bit reader at `0x7cbf`/`0x7ceb`, counts
      built from 2-bit groups, and eight bytes of the stream copied into its own code at
      `cs:[7cb7]`. Ground truth for checking it is captured: `.ish/logo-decoded.bin`,
      40,632 bytes, via `tools/t11-capture.py`.*

- [x] **T12 · Palette**
      Capture the DAC at the language menu; establish where the palette comes from —
      part of the asset, a separate file, or code.
      **Done when:** FORMATS.md states the palette source, and a decoded image rendered
      with it matches the emulator's colours.
      *An asset carries colour indices only; the palette is loaded separately, and the
      wrong one gives a correct picture that looks broken.*
      *Met. The palette is **part of the asset**: a 772-byte record, `fe ff 00 00` followed
      by 256 8-bit RGB entries (FORMATS.md 3.9, T11j/T11m4). Only 9 of ~110 assets carry
      one; the rest borrow. And the match is exact rather than approximate -- reading the
      framebuffer at 0xA0000 and colouring it with the palette recovered from `fond.io`
      reproduces the running game's screen, `captures/t11m2-vram.png` against
      `captures/t11m2-state.png`.*

- [ ] **T13 · The menu's glyphs**
      The language menu's text is drawn in stylised glyphs, so there is a font asset and
      a text routine. Find both.
      **Done when:** the glyph set is decoded to a PNG sheet in `captures/`, and the
      routine that places them is annotated.
      *Ruled out so far, none of it repeatable: the glyphs are **not a chained sprite bank**
      -- no asset holds many small same-height sprites, the closest being `buste` (29 at
      height 44, the portraits) and `frise` (10 at 17). They are **not a 1bpp bitmap** in any
      of the eight zero-sprite assets (`blancpc`, `dplt`, `affobj`, `encont`, `gaz`, `souris`,
      `monstre`, `telep`), rendered at 16/32/64 wide. And `blancpc.io` -- the first file the
      game opens, stored uncompressed, which made it the best candidate -- is a **table of
      word values** (`04 00 16 00 ... 1a 00 00 20 00 0e 00`), not pixels, at 4bpp or 8bpp.
      Next: work from the code rather than the files. The menu is drawn by the launcher, so
      find the routine that walks a string and blits per character -- then its glyph source
      is whatever it indexes. `captures/menu-language.png` gives the target.*

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

- [ ] **T18b · Spice86's missing FPU opcodes**
      `0xDA` faults as an invalid opcode; Spice86 supports only parts of `D9`, `DB`,
      `DD` (FINDINGS §5.2). The game reaches floating-point code, so measurement runs
      die there — and §5.0's "modrm mod=3" fault looks like the same cause.
      **Done when:** it is known which escapes the game actually executes and how often,
      and a decision is recorded: implement them in the local Spice86 checkout, avoid
      those paths, or live with it. If implementing, the check is that a run which
      previously faulted now passes the same point.

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
      *Cheaper now: T09 read the field names straight out of the game's own UI strings —
      five headline values, five attributes, eight skills (FINDINGS §1.1b). The search in
      memory now has a known shape to look for instead of an unknown structure.*
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

- [x] **T19c · Re-seed the four routines chani cannot lay out**
      `seg_0000:072d`, `seg_0000:0d98`, `seg_0941:1299`, `seg_0941:1c31` are real
      routines dropped from the listing because chani panics on them — and `0d98` is
      the launcher's timer ISR, wanted by T18.
      **Done when:** each is readable somewhere — a chani workaround, a patched
      chani-rs, or a `read_disassembly` transcript pasted into `ishar.chani` as a
      comment — and none is silently missing.
      *Met, and it simply works now. All four seed without a panic against the current
      database and decode as real routines -- the layout conflict that caused
      `layout.rs:361` was resolved by the surrounding coverage that T26/T28/T29 added.
      Coverage 49.6% -> 49.7%, `seg_0941` 1,349 -> 1,395 instructions.
      Two of them are **sound code**: `seg_0941:1299` opens `push cx / push ax / mov dx,388h`
      and `seg_0941:1c31` writes `389h` -- both OPL2 ports, which is a direct lead for T25.
      `seg_0000:0d98` is the launcher timer ISR that T18 wants.*

- [ ] **T21 · Combat: to-hit and damage**
      The UI names four combat skills — `1 HAND WEAPONS`, `2 HANDS WEAPONS`, `THROWING`,
      `SHOOTING` — and the party panel shows a LIFE bar per member, so both inputs and
      outputs are on screen and therefore in memory.
      *Method: pick a fight, find a LIFE value by intersecting `search_memory` results
      across two hits, then a `MEMORY_WRITE` breakpoint on it — the writer is the damage
      routine. Read what it reads: attacker skill, weapon, target armour. Do not infer
      the formula from watching numbers; read it from the arithmetic.*
      **Done when:** FINDINGS.md states the damage formula with the code it came from,
      and one damage value predicted in advance is confirmed in the running game.

- [ ] **T22 · Magic: spells, costs, effects**
      `CAST SPELL` is one of the party actions, and `messagee.io` carries the UI around
      it. Spell names should be in the decoded text; the cast path will be a dispatch.
      *Method: find the spell names in the decoded assets first — that is free and
      offline. Then break where mana changes to find the cost table, and where the
      target's state changes to find the effect. `chaniq unresolved` lists indirect calls
      with no known target; the cast dispatcher will be among them.*
      **Done when:** FORMATS.md or FINDINGS.md carries the spell table — id, name, cost,
      school or class restriction — and at least one effect routine is read and named.

- [ ] **T23 · Quests and world state**
      Three quests are named in the text (FINDINGS §3b: the magician's talisman, the
      exhausted witch, the rune tablets), so the game tracks their progress somewhere.
      *Method: diff memory across a quest step — decoded assets and framebuffers
      excluded, the candidate set is small — then a `MEMORY_WRITE` breakpoint on a flag
      byte to catch the trigger. If a script VM exists, its interpreter shows up as a hot
      indirect jump; if not, expect hard-coded triggers keyed on location and NPC id.*
      **Done when:** FINDINGS.md carries the quest flag map and how a trigger fires, with
      one flag watched changing at the moment the game acknowledges the step.

- [ ] **T24 · Are there character classes?**
      `messagee.io` names attributes and skills but no class names appeared in the first
      pass over its strings, so whether Ishar has classes at all — or only stat spreads —
      is unestablished. This matters for T19's record layout.
      **Done when:** FINDINGS.md answers it from the decoded text or the character
      structure, not from what the genre usually does.

- [ ] **T25 · Where the sound is**
      `start.stp` selects a sound device (`cfg_sound`: AdLib, SoundBlaster, internal
      speaker and three others, FORMATS §2) and the game programs the OPL — a boot trace
      shows writes to port `0x388`. But no sound *asset* has been identified: nothing in
      the 106 files has been shown to be music or samples, and the catalogue's filenames
      do not obviously include any.
      *Lead from T19c: the OPL driver is in `seg_0941`, not `seg_0000`. `seg_0941:1299`
      and `seg_0941:1c31` both program ports 0x388/0x389, and `seg_0000:9375`/`9386`/`9396`
      are the register-write and delay helpers (the delay loops are why `seg_0000:93a6` is
      hot in every call-count diff -- it is the FM chip, not the mouse).*
      *Method: break on OPL writes (`0x388`/`0x389`) or on the SoundBlaster ports and
      read where the data being written comes from — that pointer leads to the music
      format, whether it lives in an .io file or inside the executable.*
      **Done when:** FORMATS.md says where music and effects are stored and in what
      shape, or states with evidence that they are generated rather than stored.

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
- Combat, magic and quests reached the roadmap only after the user asked where they
  were: they had lived as playbooks in the Vault plan since the start and were never
  turned into tasks. Anything that exists only in a planning document is not on the list.
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

- [x] **T19e · Why the traced run faults in the intro when a manual run does not**
      *Renumbered from T19c, which was already taken by the chani re-seed task above.*
      Three GDB-traced boots died at `017D:194D` (§5.0) before reaching gameplay, yet
      ordinary `run.sh` play reaches Fragonir. So the fault is a property of *how we
      drive it*, not of the intro. Bisect the difference one flag at a time: GDB
      attached vs not, breakpoint armed vs not, keys from `tools/nudge.py` vs by hand,
      dummy audio, fixed clock, `--ReloadCfgGraph`.
      **Done when:** one named difference flips the outcome across two runs each way, or
      all of them are eliminated and the fault reproduces in a plain `run.sh` session
      too — in which case §5.0 is the game/FPU issue and T08 needs a different route.
      *Folded into T19d, which measured what this proposed. The premise here — "the fault is
      a property of how we drive it" — is false: it fires around 45s **regardless of audio
      flags**, and runs with identical configuration both fault and survive (FINDINGS 5.3).
      So there is no flag to bisect; the variable is timing, which is what T19d chases.*

- [ ] **T19d · The intro fault is intermittent — find what varies**
      Five faults, all in `seg_0e97:0ec6..0f2a`, all entering the ISR prologue at
      `seg_0e97:0ec9` mid-instruction, and in every case Spice86's reported opcode is not
      the byte at its reported CS:IP (FINDINGS 5.3). It fires around 45s regardless of
      audio flags, and some runs sail past it. Supersedes the FPU reading in 5.2.
      *Method: break on `seg_0e97:0ec9`, log the return address and the interrupt frame on
      every entry, and compare a run that faults against one that does not. The entry
      offset is the variable — find who calls or vectors into it at `0ec6` instead.*
      **Done when:** the caller or vector that enters the handler at the wrong offset is
      named, or the fault is reproduced on demand rather than by retrying.

- [ ] **T09e · Name the setup-phase files the T08 trace exposed**
      `souris.IO`, `objet.IO`, `gerdep.IO`, `frise.IO`, `param.IO`, `encont.IO`, `dplt.IO`,
      `scomb.IO`, `bormin.IO`, `kiriela.IO`, `samb.IO` all load between the menu and the
      first frame (FINDINGS 4.10) and none is described in FORMATS.md. `souris` is French
      for mouse, which is a lead, not evidence.
      **Done when:** each has a line in FORMATS.md saying what it holds, with the evidence
      being what is drawn or what the decoded bytes are — not the filename.

- [ ] **T08b · Why is `EN1.FIC` opened twice?**
      The trace opens `EN1.FIC`, then `TAB1.FIC`, then `param.IO`, then `EN1.FIC` again
      (FINDINGS 4.10). Both runs do it, so it is not language-related.
      **Done when:** the two call sites are distinguished and it is said what each read is
      for — a size probe, a re-read after `param.IO` changes something, or a genuine
      second load.

- [ ] **T09f · What does `S` = `C` select?**
      `cfg_sound` maps both `G` and `C` to 4, telling them apart by setting
      `seg_13d7:0b8e` to 8 for `C` (FORMATS 2). The setup screen offers only one
      Sound Galaxy entry, so `C` is a device the UI cannot choose — likely a variant
      board selected only by hand-editing `START.STP`.
      **Done when:** FORMATS 2 says what `C` is, from the code that reads
      `seg_13d7:0b8e` — or records that nothing reads it.

- [x] **T36b · Machine-verify the 4bpp sprite path**
      T36 proved the container (98/98, two implementations) and the 8bpp path against the
      live framebuffer, but 4bpp is only cross-validated between two of our own readers —
      level 2, not level 3 (FINDINGS 4.12). 4bpp is most of the game's art and is where
      the palette-group, transparency and nibble-order bugs all happened.
      *Method: as T36 — reach a screen drawn from a 4bpp asset, dump `0xA0000`, and search
      the decoded payloads for the framebuffer run **expanded the other way**: for each
      candidate base `g*16`, subtract it from the screen bytes, check every result is
      0..15, repack two-per-byte high-nibble-first and search for that. A hit names the
      file, the base and the group at once. Note the GDB reads pause the machine, so
      `cont()` after each dump or the game never advances past the logo.*
      **Done when:** one 4bpp asset is compared pixel-by-pixel against VRAM with every
      differing pixel accounted for, as `logo.io` now is.
      *Done, and it overturned FORMATS 3.13. `buste.io`'s portrait (mode 0x10, 64x36 at
      6986) matches VRAM on **1233/1233 non-zero pixels = 100.0000%**, and on **0 of 1071**
      nibble-zero pixels — those show the frieze behind, so nibble 0 is transparent. The
      key is on the **nibble**, before the base is added, which is why the old test on the
      final index could never fire. `word3 = 0x00d0` predicts base 208 and an independent
      reverse search recovered base 208 from the screen bytes, so the `word3 >> 4` group
      rule is confirmed from two directions too.
      Also learned: the outdoor viewport matches **no** asset at either depth, confirming
      T11p — it is composed with perspective scaling, not blitted. Verify against the UI
      panel, not the 3D view.*

- [x] **T36c · Find the masked 4bpp expander**
      FORMATS 3.13 documents `expand_4bpp` (`seg_0e97:0ad1`), which writes both nibbles
      with `stosw` and tests nothing. It cannot have drawn `buste.io`'s portrait, which
      the framebuffer shows skipping every nibble-zero pixel (3.13b). So a second, masked
      4bpp expander exists and is the one actually used for panel sprites.
      *Method: break on `seg_0e97:0ad1` with the party panel being drawn and see whether it
      fires at all — if it does not, that is the finding. Then find the routine that does,
      via the caller of the portrait blit, and read its inner loop for the `jz`.*
      **Done when:** the masked expander is named and annotated in `ishar.chani`, and 3.13
      says which of the two is used for which sprites.
      *Done. It is `expand_4bpp_masked` at `seg_0e97:0b63`, now annotated. The dispatcher at
      `seg_0e97:0a30` sends mode 0x10 to `0b4c` and mode 0x00 to `0b40`, and both fall into
      that loop; only mode 0x12 reaches `expand_4bpp_opaque` (0ad1), which fires 0 times in
      20s of walking against 5 for a control. FORMATS 3.13c is the full five-mode table.
      Two refinements: the base is `word3`'s low byte used directly, not `(word3>>4)*16`,
      and mode 0x00 is keyed too — so `presti.io`'s "holes" were correct all along.*

- [x] **T36d · Re-extract the 4bpp assets with correct transparency**
      Everything in `captures/assets/` rendered from a 4bpp sprite has a solid rectangle of
      `base + 0` where transparency belongs (3.13b). `tools/ioscan.py` and
      `tools/io2png.py` both need the nibble-0 key, and the PNGs need regenerating.
      **Done when:** a re-extracted portrait from `buste.io` has an alpha-zero background
      and its opaque pixels still match VRAM 1:1.
      *Done. `tools/png.py` now writes RGBA (colour type 6) when given 4-tuples, so
      transparency is a real alpha channel rather than a green sentinel — a marker colour is
      indistinguishable from a sprite that legitimately uses green. All 803 PNGs
      re-extracted. The acceptance case passes exactly: 1071 alpha-zero pixels, the same
      count the VRAM split predicted, and 1233/1233 = 100.0000% on the opaque ones.*

- [x] **T38 · Prove the `main.io` disassembly against execution**
      `tools/vmdis.py main.io --stats` reports 97% "decoded as instructions", and that number
      is worthless on its own: T37 records that 219 of 231 byte values are valid opcodes, so
      a linear walk from any offset decodes to ~100% whether or not it is aligned. T30's
      "over 80%" acceptance therefore cannot fail. This task supplies one that can.
      *Method: break on the VM fetch (`vm_dispatch`, `seg_0000:69a6`) and sample `DS:SI` --
      the script program counter -- a few thousand times across boot, the language menu and
      a walk. Every sampled SI must land on an instruction boundary in vmdis's listing. One
      that lands mid-instruction disproves the alignment for that region. FINDINGS 6.9
      already did this by hand for 10 samples over the menu; this is the same check at
      scale and automated.*
      **Done when:** `tools/vmcheck.py` reports the share of sampled `DS:SI` values that are
      instruction boundaries, it is over 99% across at least three phases, and any region
      that fails is named in FORMATS.md as not-yet-aligned rather than quietly counted.
      *Partly done (FINDINGS 4.14). The tool exists and it earned its keep immediately: it
      found that `vmdis` was reading **label lines as mnemonics**, so every handler named in
      `ishar.chani` lost its operand width — our own annotations were degrading the
      disassembler, and the 97% headline did not move when it was fixed. Gameplay phase now
      scores **34/34 = 100.000%**, and the pre-fix failure at 3352 is resolved.
      Not met: one phase, not three, and 34 samples, not thousands. Sampling **saturates** —
      the game idles through the same statements, so 140s gives the same 34 distinct offsets
      as 45s; more activity would help, more time will not. `vm_run` yields no samples at all
      during the intro or a cold boot.
      Still open: offsets 103 and 150 are not boundaries. That reading came from the weaker
      anchoring since replaced, so it is not trustworthy alone — but vmdis emits `db` at 88,
      95 and 151 independently, and offsets under ~160 are where main.io's catalogue lives
      (T11e). Decoding a catalogue as instructions would look exactly like this. See T38b.*
      *Superseded by T39d, and closed on a stronger result than it asked for. It wanted
      ">99% of sampled `DS:SI` on instruction boundaries across three phases" from
      `tools/vmcheck.py`. Traversal now reaches **100% of the statements the VM actually
      executes** (34/34 IP-verified samples) from `main.io`'s two entry points, which
      subsumes the sampling check — a boundary set that contains every executed statement
      cannot be misaligned where execution goes.
      What T38 contributed stands and is why it was worth doing: it found that `vmdis` read
      **label lines as mnemonics**, so every handler named in `ishar.chani` lost its operand
      width — our own annotations degrading the disassembler, invisible in the headline
      (97% before and after).*

- [~] **T39 · Implement the VM and run `main.io` against the emulator**
      The asset half was only ever settled by building a decoder from FORMATS.md alone and
      comparing its output to the machine (T36/T36b). The game-logic half needs the same
      gate, and nothing weaker will do: a disassembly that looks plausible is not evidence,
      for the reason T38 exists.
      *Method: implement `vm_run` and the opcodes in one file, the way `java/IsharSprites.java`
      was written from the spec alone. Start the interpreter at the same entry the game uses,
      step it, and compare its `SI` sequence -- and the engine variables it writes -- against
      a live trace of the real one. Divergence names the first opcode that is wrong, which is
      exactly the feedback the sprite work got from a framebuffer diff.*
      **Done when:** the interpreter reproduces at least 10,000 consecutive `DS:SI` values
      from a live trace with no divergence, and every opcode it had to guess at is listed.
      *Started, and it already paid for itself. `tools/vmi.py` reads all four dispatch tables
      out of the image (statement 230, load 112, store 54, add-assign 27) and steps.
      **It settled T38's two disagreements outright** (FORMATS 7.4): opcode `0x29` is a
      block initialiser of length `5 + 2*count`, count taken from its own third operand
      byte. At offset 96 its loop swallows `5a 00` and at 143 it swallows `1a 00` — so the
      `5a` and `1a` vmdis was decoding as statements are operand *data*. Next offsets 103
      and 150, which are exactly what the live VM reported. No operand-width fix could ever
      have worked, because the length is not a property of the opcode.
      Also learned: automatic width derivation is not sufficient — `walk()` gave `0x29` the
      signature `w,b,b,w` by counting the loop body's `lodsw` as a fixed operand. Handlers
      have to be read.
      Far from done. The stepper walks 138 statements from offset 96 before meeting an
      opcode it cannot size, and offset 0 is not a valid entry point (dies after 23
      statements at offset 40). The 10,000-sample live gate needs most of ~110 handlers
      modelled by hand; see T39b.*

- [x] **T29c2 · Recheck T29c's "no mouse the harness can reach" blocker**
      T29c is `[!]` because combat and magic are mouse-driven and INT 33h showed 0 calls.
      Blockers here have a poor record: T07, T10, T11g3 and T08 were all blocked on
      conditions that had stopped being true, and T11p's blocker named the wrong region
      entirely. Since it was written, `tools/ish keys` over MCP has been shown to drive the
      game reliably (T08, T36b) where `tools/nudge.py` did not.
      *Method: FINDINGS 6.4 says F1 opens the ACTION menu. Drive it with MCP keys and take
      the call-count diff `tools/t11p-diff.py` was built for. If the menu is reachable by
      keyboard, the mouse is not needed and the blocker is dead.*
      **Done when:** either ten primitives are attributed as T29c asks, or it is shown with a
      keyboard trace that combat genuinely cannot be entered without a pointer.
      *Blocker confirmed real, but **relocated and root-caused** (FINDINGS 6.4). It is not
      "the game has no mouse": traced from a cold start the game makes eight INT 33h calls
      during boot and installs an event handler, `AX=0x0c`, callback `017d:1249`, now
      `mouse_event_handler` in `ishar.chani`. The old zero-call reading came from measuring
      mid-game, after the only call that matters.
      The blocker is **Spice86's**: injected mouse input produces 0 hits on that callback and
      0 on the BIOS INT 74h handler, against 507 for a control at `vm_run`. IRQ12 is never
      raised, so the driver never reaches the callback it has correctly registered — the
      machinery is all there (`MouseDriver.cs:129-157`, `BiosMouseInt74Handler` installed).
      Also worth knowing: `send_mouse_move` takes **normalised 0.0-1.0** coordinates, not
      pixels — `{x:160,y:100}` answers "moved to (1.000, 1.000)", i.e. clamped to the corner.
      Both conventions were tried; neither reaches the callback.
      Ten primitives not attributed. **Unblocked by T29c3**, which is now a Spice86 fix
      rather than an emulation-limits argument.*

- [x] **T38b · ~~Is the start of `main.io` a catalogue rather than script?~~** — *premise dead; the real cause found instead*
      `vmdis` decodes from offset 0 and emits `db` at 88, 95 and 151; a live sample put
      instruction boundaries at 103 and 150 where vmdis has neither (FINDINGS 4.14). But
      T11e says `main.io` carries a catalogue, and offsets under ~160 are where it sits — a
      catalogue decoded as instructions produces exactly this picture.
      *Method: read the catalogue's layout from T11e/FORMATS and mark that byte range as
      data in `tools/vmdis.py` so the listing starts at the first real statement instead of
      at 0. Then re-run `tools/vmcheck.py`: if 103 and 150 fall inside the catalogue, they
      were never script and the disagreement dissolves; if they survive, the misalignment is
      real and the region needs its own entry point.*
      **Done when:** vmdis skips the catalogue, and either the two offsets are inside it —
      recorded as such — or they remain and are named in FORMATS.md as a misaligned region.
      *The premise was false and this entry was written from my own misreading. FORMATS 7
      already establishes — with live evidence — that `main.io` is **bytecode throughout**,
      not a table: opcode 0x45 carries an asset id and an inline filename as *operands*.
      The `hdr_is_catalogue` flag names a 16-byte directory in the **container header**,
      which `decode()` strips before the payload begins. There is no catalogue in the
      payload to skip, so the method here cannot be carried out.
      What the investigation did establish (FORMATS 7.3): the two offsets are **real**, and
      my earlier "untrustworthy anchoring" caveat was over-cautious — a run of nine 5-byte
      `0x29` records resumes on exactly 103 and 150, corroborating the live samples with no
      emulator involved.
      The cause is structural: **79 of 230 statement opcodes call the expression evaluator**,
      so the bytes after them are expression bytecode from the byte-scaled table at 0x01f2 —
      a different instruction set — and the statement's length is variable. A single-table
      linear disassembler cannot be right for those, which is also why "97% decoded" is
      meaningless. Getting lengths right needs an interpreter, so **T39 is now a
      prerequisite for T30**, not an extra.*

- [ ] **T38c · Get vmcheck out of its saturation trap**
      The check saturates at ~34 distinct offsets because the idle game re-runs the same
      statements, and a stop costs a pause/resume so raw time does not help.
      *Method: drive varied activity while sampling — open the character sheet, the ACTION
      menu (F1, FINDINGS 6.4), walk into a wall, change level — and merge the distinct
      offsets across runs into one cumulative set rather than reporting per-run. Consider
      sampling `vm_dispatch` (`seg_0000:69a6`) too, which T11p found is far hotter.*
      **Done when:** the cumulative distinct-offset count is over 500 and the boundary rate
      across all of them is reported as one number.

- [~] **T39b · Model the statement handlers one at a time**
      `tools/vmi.py` steps correctly where it has been taught and stops at the first opcode
      it cannot size (offset 758 walking from 96). FORMATS 7.4 shows why a scan of each
      handler's `lodsb`/`lodsw` is not enough: `0x29`'s loop body reads a word per
      iteration and the scan counted it as a fixed operand.
      *Method: order the opcodes by how often `tools/vmdis.py --stats` sees them, read those
      handlers in `ishar-listing.txt` one by one, and add each to `vmi.py` with a comment
      naming the instructions it was read from. Re-walk after each: the distance before the
      first unknown opcode is the progress measure, and it must only ever grow.*
      **Done when:** stepping from a live-verified anchor covers over 90% of `main.io`
      without meeting an unsized opcode, and each modelled handler cites its code.
      *Substantial progress, not met (FORMATS 7.2b). Coverage from the real entry (24):
      linear 173 statements -> **recursive traversal 4,811 statements, 42.8% of bytes**.
      **No stall on any in-range opcode**: all 56 remaining stalls are on bytes >230, i.e.
      data reached by a wrong branch target, not statements the stepper cannot size.
      Two fixes got it there. The dispatch-table floor was `0x100`, which threw away the
      no-op opcodes whose handler is a bare `ret` in the spare bytes at image 0x20..0x23 —
      opcode `0x04`'s entry is literally `0x0022`, and dropping it is what stalled the walk
      at offset 758. `tools/vmdis.py` has the same floor and the same hole.
      Then control flow: every branch handler is built from the same four parts (`lodsb`/
      `lodsw` width, an `inc si` skip, a `jz`/`jnz` test, a push into `es:[bp-0ah]`), so the
      shape is *derived* rather than hand-coded. It reproduces all five shapes that had been
      checked by hand against live execution.
      Also produced: the full 231-opcode table in FORMATS 7.2b, generated from the handlers
      — 85 no-ops, 105 embedding an expression, 22 branch-shaped, 2 variable-length, 165
      named in chani.
      Remaining for 90%: paths reached only by indirect jumps, and branch targets that land
      in data (the 56). Other assets stay near 0% from offset 24, which is evidence that 24
      is **not** their entry — see T37e.
      Second round: found the two statements that end `vm_run` — `0x42` (`add sp,2 / ret`,
      and the second most common opcode in main.io) and `0x43` — since a handler can only
      leave that loop by discarding its return address (FORMATS 7.2c).
      Treating them as terminal in traversal is **wrong**: coverage falls 42.8% -> 8.7%, so
      control really does continue past them, which fits them being yields that resume.
      But the confirming test fails: if a yield saved SI just past the opcode, every
      observed first-yield offset would sit one byte after a `0x42`/`0x43`, and none of the
      four does. Either those offsets are not yields, or the live-`DS:SI`-to-offset base is
      wrong. Unresolved and written down rather than guessed at. Model left at 42.8%.*
      *Third round — the 56 stalls are **fixed** (FORMATS 7.2d). Each traced back to a
      *different* branch, so it was never one wrong shape; following one bad target puts the
      walk inside data where everything after is garbage. Targets are now checked before
      being taken (231 opcodes exist, so a target outside the table cannot be code):
      **stalls 56 -> 0**, coverage 42.8% -> 42.6%, 116 targets rejected. Coverage barely
      moves because the extra 56 statements were fictional.
      Not a base error: for `0x06` base 3 gives 61/87 plausible targets against 60/60/61/60
      for bases 1-5, and `0x0a` base 4 gives 121/141 against 118-119 either side — both the
      hand-verified values.
      **New acceptance number: live coverage.** Against 34 IP-verified `DS:SI` values sampled
      at `vm_run` during gameplay, traversal hits **25/34 = 73.5%** of the statements actually
      executed. Byte coverage is the weaker measure; this is the one to move.
      The nine misses are all in-edges traversal cannot compute — 19919 is the fall-through of
      an unconditional jump, so it is reached from somewhere else entirely. See T39d.*

- [x] **T39c · Find `main.io`'s real entry point**
      Stepping from offset 0 dies after 23 statements at offset 40, so the file does not
      begin with executable script. The live anchors that do work were found by matching
      bytes against a running `DS:SI`, which needs the emulator.
      *Method: the loader calls the script somewhere — find where `vm_run` is first entered
      after `MAIN.IO` is read (the trace in FINDINGS 4.10 gives the moment) and record SI at
      that first entry. That offset is the entry point, and it is also the shape of the
      answer T37 needs for every other asset.*
      **Done when:** the entry offset is recorded in FORMATS section 7 and stepping from it
      reaches at least as far as stepping from offset 96 does.
      *Met. The entry is **offset 24** (FORMATS 7.5). The first six live entries to `vm_run`
      are 24, 60, 96, 103, 108, 113 and `tools/vmi.py` reproduces all six offline; stepping
      from 24 covers 140 statements against 138 from 96, reaching the same offset 758.
      Two things fell out. The statements at 24 and 60 are opcode `0x46`, 36 bytes each —
      `rep movsb` copying a 32-byte record inline — now modelled in the stepper.
      And **scripts are resumable coroutines**: the caller does `lds si,es:[bp-8]` / `call
      vm_run` / `mov es:[bp-8],si`, so a script's PC is a far pointer in the frame. The entry
      point is whatever is stored in that slot, not a constant — so *finding who first writes
      `es:[bp-8]` is the general form of T37's question*, and it is the same one breakpoint
      for every asset.*

- [x] **T37b · Who writes `es:[bp-8]`? The general entry-point question**
      T39c found that a script's program counter is a far pointer in the frame at
      `es:[bp-8]`, restored by `lds si,es:[bp-8]` before each `vm_run` and written back
      after (FORMATS 7.5). So an asset's script entry point is whatever put a pointer in
      that slot — not a constant, and not necessarily in the asset header.
      This is T37's blocker ("vmdis has no entry point") asked in a form that a single
      breakpoint answers, for every asset at once rather than one at a time.
      *Method: MEMORY_WRITE on the frame slot, or break on the routine that sets it, and
      record the far pointer written together with which asset was most recently loaded.
      Match each pointer against the decoded assets the way `tools/t39c-entry.py` does.*
      **Done when:** for at least three assets other than `main.io`, an entry offset is
      recorded in FORMATS and stepping from it with `tools/vmi.py` runs without meeting an
      unsized opcode sooner than `main.io` does.
      *Partial, and it moved T37 a long way (FORMATS 7.6). Three assets are now **observed
      executing bytecode**: `frise.io` (60 distinct PCs), `dplt.io` (39) and `main.io` (34),
      with every sample attributed and none ambiguous under the strict match (64-byte run,
      unique in its asset, absent from all 97 others). `frise.io` is the UI frieze and
      `dplt.io` was unclassified — so T37's "the unexplained bytes are consistent with
      bytecode" becomes "these assets are running bytecode".
      Entry points: `main.io` **24**, `logo.io` **24**, both from a paused cold start where
      the first `vm_run` entry is by construction the entry.
      **Not** established: that 24 is universal. Stepping all 98 assets from a given offset
      gives median 17 statements from 24 but 25 from 16 and 23 from 18 — offset 24 scores
      *worse* than its neighbours, because with 219 of 231 valid opcodes any start decodes
      for a while. The test cannot pick an entry point; only the live observation can.
      Static `es:[bp-8]` analysis was a dead end: six sites, three writes, all script-level
      call/return (`add ax,si`), and nothing writes the segment half at `bp-6` at all.
      Remaining: run the cold-start scan far enough to catch `frise.io` and `dplt.io`'s
      first entries — see T37c.*
      *Closed into T37f. The static route is a dead end and is recorded as such: `es:[bp-8]`
      has six sites, the three writes are all script-level call/return, and nothing writes
      the segment half at `bp-6`. What replaced it — first `vm_run` entry from a paused cold
      start — is now T37f's method.*

- [x] **T37c · Catch the first `vm_run` entry for assets loaded after the menu**
      T37b established the method — from a paused cold start the first `vm_run` entry for an
      asset is its entry point — and got `main.io` and `logo.io`, both 24. `frise.io` and
      `dplt.io` demonstrably run script but were only caught mid-execution, so their entries
      are unknown. The scan reached only ~78s of emulated boot in 270s of wall clock because
      every `vm_run` entry is a breakpoint stop.
      *Method: arm the breakpoint late rather than from the start — run unattended to the
      first gameplay frame, then attach and clear, so the first entry seen per newly-loaded
      asset is still its entry. Or condition the breakpoint on DS so only unseen script
      segments stop.*
      **Done when:** entry offsets are recorded for `frise.io` and `dplt.io`, and it is
      stated whether they are 24 — which would make the entry a constant and close T37's
      entry-point question for the whole corpus.
      *Not met, but the instrument problem behind it is solved and the evidence for T37 grew
      a lot (FORMATS 7.6).
      The blocker was measured rather than guessed: a breakpoint on `vm_run` stops once per
      **statement** — its loop jumps back to its own entry — and that stalls the game
      completely. 270s of wall clock with **0.0% of the screen changed**; the game cannot
      reach the state being looked for while the probe is attached.
      Fix: `mov es:[bp-8],si` (`seg_0000:26b2`) runs only when `vm_run` *returns*, so a
      MEMORY_WRITE on the script-PC slot fires once per **yield**: `tools/t37d-switch.py`
      gets **164 stops/s against 2.6**, and the game runs normally. The slot sits at a fixed
      linear address (`0x12948`) that is stable across runs.
      With it, **ten** assets appeared to be running script rather than three — including
      `blancpc.io`, `fond.io` and `presti.io`.
      **RETRACTED (T39b).** That probe is unsound. At a MEMORY_WRITE stop the slot does not
      contain `SI`: 4 stops agreed, **5,868 did not**, with the slot constant at `0x144d`
      while SI wandered. So `DS:SI` read at such a stop is not the script PC and every
      offset and asset name it produced is meaningless. An execution breakpoint can be
      validated against `ip`; a memory breakpoint cannot, so the guard has to be "read the
      watched location and check it matches the register". Only the IP-verified assets
      stand: `main.io`, `logo.io`, `frise.io`, `dplt.io`.
      Still open: those offsets are **yields, not entries** (`main.io` reads 256 there and 24
      from a cold start), and neither `frise.io` nor `dplt.io` appeared in the window. See
      T37e.*
      *Closed into T37f. Its instrument, `tools/t37d-switch.py`, was retracted: at a
      MEMORY_WRITE stop the slot does not contain `SI` (4 stops agreed, 5,868 did not), so
      the ten assets and the yield offsets it produced are meaningless. The IP-verified
      result stands — five assets run script: `main.io`, `logo.io`, `frise.io`, `dplt.io`,
      `samb.io`.*

- [x] **T37e · Entry points, now that a cheap probe exists**
      T37c built `tools/t37d-switch.py` (164 stops/s, game runs normally) and used it to
      find ten assets running script, but its offsets are yield points. An entry point needs
      the *first* write of a script's PC, not any write.
      *Method: at each stop the slot's previous value is known — keep it. A write whose new
      pointer lands in an asset that has not been seen before, or whose segment:offset is
      discontinuous with the previous PC, marks a script starting rather than resuming.
      Record that. Run it from a cold start through to the first gameplay frame, which is
      now affordable.*
      **Done when:** entry offsets are recorded for at least three assets besides `main.io`
      and `logo.io`, and it is stated whether 24 is the constant entry for all of them.
      *Blocked on **T39b**, and the dependency is the finding (FORMATS 7.6). A cold-start run
      gives each asset's first *yield* — `main.io` 256, `logo.io` 256, `blancpc.io` 801,
      `fbuis.io` 3960 (an eleventh asset running script). Tying a yield back to an entry
      means stepping from the candidate entry and checking the walk reaches it; that fails
      for all four because `tools/vmi.py` walks **linearly** and scripts reach their yields
      through jumps — `main.io`'s walk covers offset 758 without ever touching 256.
      So entry points are not a tracing problem any more. They need a stepper that follows
      control flow, which needs the handlers modelled (T39b). Three approaches have now
      failed for three different reasons — static `es:[bp-8]` analysis, filtering by segment
      (assets share `DS=1cf3`), and yield corroboration — and only the expensive
      statement-level breakpoint from a cold start works, which stalls the game before the
      later assets load.
      **Do T39b first.** This entry is not ready.*
      *Update after T39b's traversal landed: still not reached. Traversing `main.io` from 24
      covers 4,811 statements and 42.8% of bytes but **does not pass through its first yield
      at 256**, and `logo.io`, `blancpc.io` and `fbuis.io` traverse to 0.1-1.4% from 24 —
      which is itself evidence that **24 is not their entry**. Whatever sets a script's
      initial PC is still the missing piece.*
      *Closed into T37f. Its blocker is gone: T39d supplied control-flow traversal, and the
      answer it produced changes the question — `main.io` has **two** entry points (24 and
      19919), the second a region with no static in-edge from anywhere in the file. So an
      asset has a *set* of entry points, not one, and that is what T37f asks for.*

- [x] **T39d · The in-edges traversal cannot compute**
      Traversal from `main.io`'s entry reaches 73.5% of the statements the VM actually
      executes (FORMATS 7.2d). All nine misses are places reached by an **incoming edge**
      that is not a static displacement — 19919 is the fall-through of an unconditional
      jump at 19915, so nothing on that path reaches it.
      Two candidates, and they are distinguishable: scripts have **more than one entry**
      (an event handler resumed by the engine, which 7.5's `es:[bp-8]` model allows), or
      some branch target is **computed** rather than an immediate.
      *Method: for each missed offset, look for a static displacement anywhere in the file
      that would land on it — if one exists, the branch opcode carrying it is unmodelled;
      if none does, the offset is an engine entry point and belongs with T37e.*
      **Done when:** live coverage of `main.io` is over 90%, or each remaining miss is
      classified as computed-branch or engine-entry with the evidence.
      *Met, both ways (FORMATS 7.2e). The misses are **engine-entry**: five of the nine have
      zero candidate in-edges anywhere in the file and the other four are reachable only from
      those, so the region is a closed subgraph nothing in the script jumps into. Adding
      **19919** as a second entry takes live coverage from 25/34 to **34/34 = 100.0%** and
      byte coverage 42.6% -> 47.0%, still with no stalls.
      The wider lesson: **a script has more than one entry point.** T37e should be looking
      for a set per asset, not a single offset.*

- [x] **T39e · Why do only 70% of `0x06` targets land on an opcode?**
      231 of 256 byte values are valid statement opcodes, so ~90% of *random* targets pass
      the "is it an opcode" test. `0x06` (script call, d16 base +3) manages 61/87 = 70%,
      which is worse than chance and says those sites are being decoded at PCs that are
      themselves wrong (FORMATS 7.2d).
      **Done when:** it is established whether the sub-chance rate comes from bogus `0x06`
      sites reached down a wrong path, or from `0x06` targets being computed rather than
      immediate — with a count either way.
      *Met: **bogus sites**, count 47 of 257 `0x06`/`0x0a` sites (FORMATS 7.2f). Evidence,
      three ways: the displacement is a signed immediate (signed 72.7% valid vs unsigned
      52.5%, so not computed); 26 of `0x06`'s 27 failures target *outside the file*, and a
      script call cannot leave its own buffer; and **57% of the 47 failing sites carry `0x42`
      as their operand's high byte** — the terminator opcode being eaten as half a
      displacement, which is the signature of starting a statement at the wrong byte.
      For contrast `0x14` is 178/178 = 100% against a 90.2% chance baseline, so its shape is
      certainly right. The 7.2d target check already stops these propagating.*

- [x] **T29c3 · Make Spice86 deliver injected mouse input to the game**
      T29c2 root-caused the mouse blocker: the game registers an INT 33h event handler at
      `017d:1249`, Spice86 registers it correctly and has the code to call it
      (`MouseDriver.cs:129-157`), but injected moves and clicks never raise IRQ12, so
      `BiosMouseInt74Handler` never runs and the callback is never reached. Measured 0 hits
      on both against a live control of 507.
      This is the gate on combat, magic and inventory — T29c, T21, T22 and T23 all wait on
      it — and it is a change to a checkout we own rather than a limit of the game.
      *Method: follow `send_mouse_move`/`send_mouse_button` from the MCP layer into the
      mouse device and find where a real pointer event would set `LastTrigger` and raise
      IRQ12; the driver's own gate is `(LastTrigger & TriggerMask) == 0`, so the trigger
      mask the game passed with `AX=0x0c` is worth logging too. Prefer a fix in Spice86
      over faking INT 33h returns, so the game's own code path runs.*
      **Done when:** a breakpoint on `seg_0000:1249` fires while the harness injects mouse
      movement, and clicking a visible ACTION-menu entry changes the screen.
      *Met, both halves. The fix is one line each for `Mouse` and `MouseDriver` in Spice86's
      `Spice86DependencyInjection.cs`: they subscribed to `_gui as IGuiMouseEvents` while the
      keyboard subscribes to `inputEventHub`. Injected events went into the hub with nothing
      listening, and in headless mode `_gui` is `HeadlessGui`, which "never raises these
      events". Passing `inputEventHub` (which wraps the GUI, so real input is unaffected)
      makes the chain work. Committed in the Spice86 checkout as `d3b54587`.
      Result: the callback fires with `AX=1` on movement (0 before), the game's cursor
      appears and tracks the pointer, and clicking MAP opened the world map of KENDORIA —
      65.4% of the screen (`captures/t29c3-map-clicked.png`).
      **This unblocks T29c, T29d, T29c2 and with them T21 (combat), T22 (magic) and T23
      (quests)** — the entire game-logic half of the project.*

- [x] **T40 · Where do on-screen positions come from?**
      FINDINGS 4.15 maps every UI region to its asset — `frise.io` for the chrome at three
      palette bases, `buste.io` for portraits — but every screen origin in that map was
      *measured* from a framebuffer, not derived. A rewrite needs the layout, not just the
      pixels.
      *Method: the sprite blitter takes its destination from a pointer and its coordinates
      from somewhere; break on the mode-0x10 path (`seg_0e97:0b4c`) with the panel drawing
      and record the destination offset alongside the sprite's own header, then find which
      script statement or engine variable supplied it. Opcode `0x29` (a block initialiser
      writing into the engine variable block) is a candidate source.*
      **Done when:** the portrait's screen origin (0, 147) is predicted from data in the
      file or from a named engine variable, rather than measured.
      *Not met, and it has a prerequisite nobody had noticed (FINDINGS 4.18). Three
      negatives: positions are **not precomputed offsets** — `147*320 = 47040` appears
      nowhere in the executable and only twice in 98 assets, both inside image data — so a
      destination is computed at draw time from x and y.
      The method above names `seg_0e97:0b4c`, but that whole sprite family takes **0 hits**
      in game against a control of 44, consistent with T11p finding `seg_0e97:038b` firing
      445 times in the intro and zero while walking. FORMATS 3.13c's *format* is right
      (`buste.io` decodes byte-for-byte as mode 0x10) but its *code* is the launcher and
      intro renderer. **The in-game blitter is unidentified**, and that is the real blocker
      — see T40b.
      Also learned: breakpoint probing of draw routines defeats itself — 5,000–6,000 stops in
      20s slow the machine so the click never processes. Identify the routine with the
      call-count diff first, which does not stop the machine.*
      *Met (FORMATS 3.17). `sprite_dest_compute` (`seg_0e97:0371`) computes
      **dest = base + Y*stride + X** from `ss:[1dbf]` (base, read live as `0000:e000`),
      `ss:[1dd5]` (stride, `0x0140` = 320), `ss:[0c2e]` (Y) and `ss:[0c2c]` (X).
      Polling those two while the panel redraws yields **x=0, y=147** — exactly the portrait
      origin proven byte-for-byte against VRAM in 3.13b — so the position is now derived
      rather than measured. Other panel positions fall out of the same poll: (0,139),
      (24,157), (0,175), (14,199), (31,152).
      Method note: polling memory works where breakpoints did not. A bare breakpoint here
      drowns in ~340 background stops/second — measured with a breakpoint on an address that
      never executes, which still produced 4,088 stops in 12s — and each one costs a full
      register read, which is what stalled the machine in three earlier attempts.
      Open follow-on: **who writes those two variables** — script or engine layout code. That
      is where a rewrite's layout data would come from. See T40c.*

- [ ] **T29g · Attribute VM opcodes, not x86 routines**
      *Renumbered from T29e, which collided with the pointer task now closed above.*
      T29c's call-count diff works at the x86 level but buries VM primitives: a UI action is
      one or two script statements against thousands of engine calls, so only 2 of ~231
      opcodes surfaced across four actions (FINDINGS 4.16).
      *Method: count opcodes directly instead. `vm_run` (`seg_0000:26eb`) has the opcode byte
      in the stream at `DS:SI`, so a breakpoint there histogrammed by `d[SI]` gives an exact
      per-action opcode profile — expensive per stop (2.6/s) but an action is short. Or use
      the traversal: `tools/vmi.py` can now reach 100% of executed statements from the two
      entries, so the statements between two live `DS:SI` samples are computable rather than
      sampled.*
      **Done when:** ten opcodes are attributed to named actions with counts, and each is
      annotated in `ishar.chani`.

- [~] **T29f · Get into a fight**
      Combat cannot be attributed without combat. Clicking ATTACK with nothing adjacent
      changes almost nothing on screen and moves no interesting counts (FINDINGS 4.16).
      There is a figure visible in the Fragonir starting scene that may be an NPC or a
      monster.
      *Method: walk toward the figure with the mouse now working, or use the map to find a
      populated area; `tools/t29c-action.py` is ready once a fight starts. Watch the LIFE
      bars for the confirmation that damage is being taken.*
      **Done when:** a screenshot shows combat under way (a monster in the viewport and a
      LIFE bar changing), and one call-count diff is taken across an attack.
      *Not met — no monster, no LIFE bar moved — but the attempt produced three findings and
      two opcode attributions (FINDINGS 4.17).
      The figure in the Fragonir scene is an **NPC**: walking into it brings up dialogue
      naming Angarahn and a tavern. **ATTACK is two-step** — the button alone only dismisses
      a panel; ATTACK then a click on the target is what acts. And attacking a friendly NPC
      triggers a **full-screen demon frame and resets the party to its start position**,
      which is Ishar's murder-consequence system, observed.
      Attributed: `vm_op_15` (0x15, 7,805 calls on an attack against 0 idle -- named
      `vm_op_attack_swing` here at first, since disproved by its 8 uses in `affobj.io`) and
      `vm_op_consequence_event` (0x57, 96 calls at the demon frame, absent from every other
      action measured). Both named in `ishar.chani`.
      Blind exploration is **not** a method: twelve rounds of six forward steps ended against
      a hedge with the frame changing 0.0–0.3%. Finding a monster needs data, not walking —
      see T29h.*

- [x] **T37f · The entry points of every script-carrying asset**
      *Replaces T37b, T37c and T37e, which were three descriptions of one question and each
      carried a stale premise. Consolidated so the next reader inherits one account.*

      **What is known.** Five assets are confirmed running VM script, all from `vm_run`
      breakpoints where `ip == entry` was checked: `main.io`, `logo.io`, `frise.io`,
      `dplt.io`, `samb.io`. Entry points are known for two — `main.io` at **24 and 19919**,
      `logo.io` at **24**.

      **What changed the question.** An asset has a *set* of entry points, not one. `main.io`'s
      second region has no static in-edge from anywhere in the file: five of its statements
      have zero candidate in-edges and the rest are reachable only from those, so the engine
      enters it directly (FORMATS 7.2e). Traversing from 24 alone reaches 73.5% of executed
      statements; adding 19919 reaches 100%.

      **What is ruled out**, so it is not retried:
      - *static analysis of `es:[bp-8]`* — six sites, three writes, all script-level
        call/return, and nothing writes the segment half at `bp-6`;
      - *filtering by segment* — assets share the script buffer (`DS = 1cf3`), so excluding
        `main.io`'s segment excludes every script (verified against a control that fires);
      - *a `MEMORY_WRITE` probe on the PC slot* — at such a stop the slot does not contain
        `SI` (4 agreed, 5,868 did not), so anything read there is meaningless;
      - *offset 24 as a universal entry* — stepping all 98 assets from a fixed offset gives
        median 17 statements from 24 against 25 from 16, i.e. worse than its neighbours.

      *Method: the only instrument that works is the expensive one — a `vm_run` execution
      breakpoint from a paused cold start, where the first entry seen for an asset is its
      entry by construction, with `ip` checked at every stop. It costs ~2.6 stops/s and
      stalls the game, so reach each asset's load moment first and arm it there. For second
      and later entries, use the in-edge test instead: a reached region with no static
      displacement landing on it from anywhere in the file is engine-entered.*
      **Done when:** entry-point sets are recorded in FORMATS for `frise.io`, `dplt.io` and
      `samb.io`, and `tools/vmi.py` traversing from each set reaches over 90% of that asset's
      IP-verified live `DS:SI` samples — the measure that worked for `main.io`.
      *Met, at **100%** for all three, and for four more besides (FORMATS 7.7).
      The method changed: **poll, do not break**. `read_cpu_state` runs at ~3,550 samples/s
      with the game unaffected, against ~2.6 useful stops/s for a breakpoint drowning in
      ~340 background stops/s. `SI` is only the script PC while the CPU is inside `vm_run`'s
      fetch loop, so samples are kept only when `CS == load` and `IP` is in `0x26eb..0x26f8`
      — without that filter the poll attributes any moment `SI` points into a buffer, which
      is not execution. One 215s cold-start run: 765,027 samples, 15,555 inside `vm_run`,
      19 assets.
      Entry sets cover every observed PC: `frise.io` 41/41 (68.7% of bytes), `dplt.io` 26/26
      (70.3%), `samb.io` 18/18, `geren.io` 29/29, `param.io` 18/18 (63.0%), `affobj.io` 17/17
      (**62.6%**, and it was 0% — that is T33's question answered), `encont.io` 24/24 (67.3%).
      **An asset has a set of entries, not one**: traversing from 24 reaches 0% of observed
      execution in seven of them.
      Honest limit: a polled first-sighting is an **upper bound**, not proof of the engine's
      entry — `logo.io` reads 68 here against the 24 proven by breakpoint. They are sound as
      traversal seeds, which is what the disassembler needs. `main.io` came out at exactly 24,
      which is the validation.
      **A static substitute was tried for the assets that never run, and it does not work.**
      `tools/t44-entries.py` traverses from every offset that could start a statement and
      keeps the ones whose region closes cleanly; scored against `encont.io`'s known set it
      picks 44/45/48 covering 13 bytes and misses every real entry. Ranking by bytes covered
      instead is no better -- `encont.io`'s real entries rank 58th to 1903rd out of ~2,000.
      Real regions contain statements the stepper cannot size and branch targets it rejects,
      so "clean" and "large" are both the wrong signal. `monstre.io` and `telep.io` still have
      no entries and the only route to them is making them execute; `dead.io` no longer needs
      one, being a picture rather than a script (T48).*

- [ ] **T42 · The input model of the boot sequence**
      The boot sequence is **input-gated, not timed** (FINDINGS 4.9, corrected): left alone
      it stops after the first frame; driven with a key each second it advances through four
      stages. So the wall times recorded for it are an artefact of the tracer, and a
      recreation needs to know what advances each stage instead.
      *Method: `tools/t42-timeline.py` already logs transitions without a breakpoint. Run it
      sending only one key at a time — Escape alone, then Space alone, then Return alone —
      and see which stages advance under which. Then leave one stage running for several
      minutes to test for a timeout, since the intro is reported to loop back to the menu
      unattended.*
      **Done when:** FINDINGS names, for each stage from the Silmarils logo to the language
      menu, the key that advances it and whether it also times out.

- [ ] **T43 · The intro after language selection — the gate and Krogh**
      Everything documented about the boot sequence stops at the language menu. What follows
      — the door/gate frame, the fire, the hooded figure — is undocumented: no asset names,
      no order, no idea whether it is script-driven like the splash.
      *Method: the same file trace that produced FINDINGS 4.10 but continued past selection,
      now that `tools/t42-timeline.py` can timestamp transitions cheaply and the intro fault
      (5.3) aborts a trace in ~2s rather than wasting a budget.*
      **Done when:** FINDINGS lists the intro's assets in load order with the screen each
      one produces, as 4.9 does for the splash.

- [~] **T29h · Find where the monsters are, from the data**
      T29f established that wandering does not work — terrain blocks movement and twelve
      rounds of walking ended against a hedge. Finding a fight should come from the files.
      Three untried leads, all cheap and offline:
      `encont.io` is loaded during engine setup and its name reads as *encontre* (encounter);
      `monstre.io` is literally "monster" and sits at 0% accounted for; and the world maps
      `cont*.fic` are 90x54 grids whose cell values are half-decoded (T11g3).
      *Method: decode `encont.io` and `monstre.io` and look for structure that pairs a map
      cell or region with a creature id — a table of small records, or ids matching the
      monster sprite assets (`zombi.io`, `azal.io`, `dealer.io`). Cross-check any candidate
      against the map grid the party actually stands on (T11g3b).*
      **Done when:** a location is named where a monster should appear, the party is driven
      there, and a screenshot shows the creature — closing T29f.
      *Not met, and the premise was half wrong (FORMATS 3.16). `encont.io`, `monstre.io`,
      `telep.io` and `dead.io` are **scripts, not tables** — each begins with the 16-byte
      header then `vm_op_block_init`, exactly like `main.io` — so there is no record layout
      to read and monster placement is code. A scan for `vm_op_load_asset` finds **zero**
      inline filenames in any of them, so they refer to things by id.
      Sizes cluster like fixed script slots: `monstre.io` and `telep.io` both 2,016 bytes,
      `dead.io` and `auteur.io` both 448. And `dead.io` is the death *script* — too small at
      448 bytes to be the demon frame it shows (FINDINGS 4.17).
      The fixed data is in the `.fic` files: `cont1..6.fic` are **exactly 90x54** (4,860
      bytes each, confirming T11g), and `en1.fic` — loaded twice at setup, `EN` reading as
      *ennemis* in a French codebase — holds ~30 small big-endian words in the 6..50 range
      after a 56-byte zero run. That is stat-block or per-entity-count shaped, not
      coordinate shaped.
      Two leads left, both offline: `en1.fic`'s word array, and the `cont*.fic` cell values
      (T11g3, still half-decoded).*

- [x] **T40b · Identify the in-game sprite blitter**
      FORMATS 3.13c documents a five-mode sprite dispatcher in `seg_0e97`, and it draws the
      launcher, title and intro — but **not the game**: it takes 0 hits while the ACTION menu
      opens and closes, and T11p separately found its blitter firing zero times in 30s of
      walking (FINDINGS 4.18). So the routine that puts portraits and UI chrome on screen
      during play is unknown, which blocks T40.
      *Method: `tools/t29c-action.py` — it does not stop the machine, so the action actually
      happens. Diff an idle window against one where the ACTION menu is opened, and against
      one where a portrait is clicked; the routines common to both and absent from idle are
      the drawing path. `ui_menu_draw_loop` (`seg_0000:35ae`, 4,248 calls) and
      `seg_0000:038b` are the current candidates. Confirm by breaking on the winner only
      once its address is known.*
      **Done when:** a breakpoint on the candidate fires while the party panel redraws in
      game, and the routine is named in `ishar.chani` with its destination register.
      *Identified: **`seg_0e97:038b`**, now `sprite_blit_ingame` — 120 calls on a portrait
      click against 0 idle, 106 on an ACTION menu draw, 112 on MAP, 23 on an attack. Its
      destination comes from the far pointer at `ss:[0bc8]/[0bca]`.
      Established by call-count diff rather than a breakpoint: three breakpoint attempts all
      returned 0 hits because 5,000–6,000 stops in 20s slow the machine so much the keypress
      never processes. The diff does not stop the machine, which is why T40's note said to
      use it first.
      **It also found a bug in my own tools**: both diff tools keyed call counts on the
      **offset alone**, discarding the segment. Five segments are in play and two offsets
      appear in more than one, so `seg_0e97:038b` was reported as `seg_0000:038b` — and
      FINDINGS 4.16's `:0008` and `:01a8` are likewise `seg_0e97`. Both tools now key on
      (segment, offset); FINDINGS 4.18 carries the correction.
      This also reconciles T11p, which found the same routine firing 445 times in the intro
      and **zero while walking**. Both hold: it draws the **UI**, not the **viewport**. And
      the in-game path reaches it **without** `sprite_mode_dispatch` (0 hits), so there are
      two entries into the sprite code.*

- [x] **T40c · Who writes the sprite X/Y variables?**
      T40 established that a sprite's destination is `base + Y*stride + X` with X in
      `ss:[0c2c]` and Y in `ss:[0c2e]` (FORMATS 3.17), and that the portrait's (0,147) can be
      read from them. What sets them is unknown: engine layout code, or the script via an
      opcode.
      *Method: grep `ishar-listing.txt` for writes to `0c2c`/`0c2e` — reads dominate, so the
      writers should be few. If a VM handler is among them, that opcode is the script-level
      "set draw position" primitive and the layout is data after all; if only engine code
      writes them, the panel layout is hardcoded and a rewrite should copy the constants.*
      **Done when:** FORMATS names the writer(s), and says whether panel layout is data or
      code.
      *Met: **layout is data** (FORMATS 3.17). `draw_pos_from_entity` (`seg_0000:469a`, and
      again at `4768`) reads X and Y from a per-entity record at **`[di+0x0c]`** and
      **`[di+0x0e]`** and writes them to the draw origin, clamped to `ss:[0c62]`/`[0c64]`.
      The records come from the script: `vm_op_declare_entity` (opcode 0x46) copies a 32-byte
      inline record into a structure at `es:[bx+6]`.
      It also corrected T40's reading of the two variables. `draw_bbox_reset`
      (`seg_0000:4179`) initialises `0c2c`/`0c2e` to `0x7fff` and `0c30`/`0c32` to `0x8000` —
      +MAX/-MAX — with `cmp`/`mov` min updates at `41db`/`41f8`. They are the **top-left of a
      draw bounding box**, not a plain x/y, which is why polling them yields each element's
      origin as it is drawn.
      Left open: which byte of the 32-byte inline record becomes `+0x0c`. The copy lands at
      `+6`, so it should be record byte 6, but that assumes DI and BX index the same
      structure — unchecked. See T40d.*

- [ ] **T40d · Which byte of an entity record is its X?**
      T40c showed a drawable's position is read from `[di+0x0c]`/`[di+0x0e]`, and that the
      records are built by `vm_op_declare_entity` (0x46) copying a 32-byte inline record to
      `es:[bx+6]` (FORMATS 3.17, 7.4). If DI and BX index the same structure, X is record
      byte 6 and Y byte 8 — but that is an assumption, and it is the one a rewrite would
      depend on to read layout straight out of `main.io`.
      *Method: `main.io`'s first two statements are both 0x46, at offsets 24 and 60, so their
      32-byte records are in hand. Predict each entity's X,Y under the byte-6/byte-8 reading
      and check the predictions against positions polled from `ss:[0c2c]`/`[0c2e]` while that
      entity draws — the technique that closed T40. A hit on two entities settles it.*
      **Done when:** FORMATS states the record's X and Y offsets, with a prediction from the
      file matching a polled position.
      *Blocked on **T37f**, and the reason is the finding (FORMATS 3.17). `main.io` contains
      only **two** genuine `0x46` declarations — the eight the traversal finds include six
      misaligned decodes, with ids reading 3840, 12311, 30720 — and both genuine ones hold
      what look like **rectangles**: (127,86)-(255,125) and (0,199)-(319,199). The second
      pair is the bottom-right of a 320x200 screen, so these are clip or viewport rects, not
      the portrait or the frieze.
      Neither candidate offset reading matches a polled position: `+0x0c` as record byte 6
      gives X=86 and 199 with Y=0 for both; as byte 12 it gives (255,125) and (319,199).
      So **the panel's entity records are in another asset's script**, and reading them needs
      that asset's entry points. The mechanism from T40c stands; the data is out of reach
      until T37f lands.*
      *Unblocked: T37f landed. `frise.io` now traverses from entries [478, 27826, 29024,
      32526] covering 68.7% of its bytes, and it is the asset that draws the panel chrome
      (FINDINGS 4.15), so its `0x46` declarations are where the panel's positions should be.*
      *Result: **they are not** (FORMATS 3.17). The entity block is found and the mechanism
      confirmed — `ss:[0bf6]` reads live as `126b:02a0`, a declaration's word operand indexes
      it, and `main.io`'s two records sit there verbatim: (127,86)/(255,125) at +24/+32 and
      (319,199) at +84. But the block is **zero beyond +128**, so only those two entities
      exist, and no (x,y) in it matches a polled panel position. Nor does any byte offset in
      the `0x46` records of `frise.io` (20 declarations), `buste.io` (29) or `main.io` (8).
      So `draw_pos_from_entity` serves those two rectangles, and the panel's sprites are
      positioned by one of the **other** writers of `ss:[0c2c]`/`[0c2e]` — `seg_0000:469d`/
      `46b6` (clamped) or `4768`-`4772`. See T40e.*

- [~] **T40e · Which writer positions the panel sprites?**
      T40d ruled out entity records: the entity block at `126b:02a0` holds only `main.io`'s
      two rectangle entities and nothing matching a panel position (FORMATS 3.17). The
      panel's coordinates therefore come from one of the other writers of `ss:[0c2c]`/
      `[0c2e]` — `seg_0000:469d`/`46b6`, which clamp against `ss:[0c62]`/`[0c64]`, or the
      unclamped pair at `4768`-`4772`.
      *Method: `tools/t29c-action.py`, which does not stop the machine — diff an idle window
      against a portrait click and see which of those routines moves. `seg_0000:4197` and
      `:4115` already showed up in that diff, and both sit in the same region. Then read what
      DI points at when that writer runs, by polling rather than breaking.*
      **Done when:** FORMATS names the structure the panel's X/Y come from, and a polled
      position is predicted from it.
      *Structure named, prediction not achieved (FORMATS 3.17). The call-count diff moves
      exactly three functions on a menu draw, all 0 idle: `seg_0000:4535` (306 calls, holds
      the clamped writer), `4723` (153, the unclamped pair) and `4170` (153, the bbox reset).
      Both writers take **DI as an input**, and the caller at `seg_0000:3f83` sets it with
      `mov di, es:[bx+2]` — the pointer `vm_op_declare_entity` stores at entity+2. So the
      chain is **declaration -> entity (at `ss:[0bf6]`+id) -> pointer at +2 -> instance ->
      `+0x0c`/`+0x0e` = X,Y**, with instances allocated from a free list at `ss:[0be8]`
      (live: `1848:0000`, ~2.9KB in use).
      **So panel layout is runtime state, not a constant in the file** — sharper than 3.17's
      earlier "layout is data": the record is data, the drawn position is an instance field.
      Not achieved: predicting a position from the instance. One pool scan put matching (x,y)
      pairs 38 bytes apart; a second found none, as the pool shifts between redraws. See
      T40f.*

- [~] **T40f · The instance structure's layout**
      T40e established that a sprite's X,Y are fields `+0x0c`/`+0x0e` of a runtime instance,
      reached from an entity's pointer at +2, allocated from the pool at `ss:[0be8]`
      (FORMATS 3.17). What the instance looks like — its size, and what else it carries — is
      unknown; one scan suggested 38-byte spacing and a second did not reproduce it.
      *Method: do not scan the pool blind. Take a single entity whose id is known from a
      `0x46` declaration, read its structure at `ss:[0bf6]`+id, follow the pointer at +2 to
      one instance, and dump that instance repeatedly while the panel redraws. Watching which
      of its bytes change identifies the live fields, and `+0x0c`/`+0x0e` should track a
      position the `ss:[0c2c]` poll sees at the same moment.*
      **Done when:** FORMATS gives the instance's size and names at least its position
      fields, with one instance's X,Y matching a simultaneously polled draw position.
      *Size and fields: done. **38 bytes**, established from the `+4` next-pointer chain
      (`0x0074` -> `0x009a`), not from a scan. Fields: +0 flags, +1 the declaration's byte
      operand, +4 next, +6 a pointer, **+0x0c/+0x0e = X/Y**, +16 the `0x7fff` bbox sentinel,
      +22..25 the record's second coordinate pair — and that last one matches the file
      exactly, (255,125) and (319,199), which confirms the instance is built from the script
      record (FORMATS 3.17).
      A trap worth recording: the pointer at entity+2 is an offset into the **pool segment**,
      not the entity segment. Read in the wrong one it yields x86 code and nonsense
      coordinates.
      Not met: matching a polled draw position. Instance X/Y run x 9..272, y 6..94 — the
      **viewport** — and none coincides with a panel-redraw position. So instances carry
      viewport object positions and the panel chrome is placed by another mechanism again.*

- [~] **T44 · What is `encont.io`?**
      It has never had a section in FORMATS, and the "*encontre* = encounter" reading that
      has been leaned on in planning is a pun on the filename, not a finding (FORMATS 7.8).
      Established: 2,008 bytes, loaded during engine setup, script not a table, 1,376 bytes
      reachable from `[47, 91, 116, 155, 291, 451, 805]`, no asset loads, and a statement mix
      nearly identical to `dplt.io`'s.
      *Method: it is now disassemblable, so read it rather than guess. Two angles — decode
      the expression operands so the engine variables it tests and writes are visible, which
      is what its `0x14`/`0x1e`/`0x1f` mix is doing; and use `tools/t29c-action.py` to find
      which game action makes its statements run, the way `ui_click_dispatch` and
      `map_decompress_inner` were attributed.*
      **Done when:** FORMATS says what `encont.io` governs, with the evidence being executed
      statements or an attributed action — not the filename.
      *Narrowed, not answered (FORMATS 7.9). It is **part of the gameplay script set**: ten
      scripts first execute within 0.3s of each other when the game proper begins, and
      `encont.io` is one of them. But it runs in **none** of idle, walking, turning or
      approaching an NPC — windows attributing 1,400-2,400 samples each, where `gerdep.io`
      takes 650-690 and `frise.io` ~350. So it starts and then waits for a trigger none of
      those actions produces, which is consistent with *encounter* without establishing it.
      Two findings alongside: `gerdep.io` is the busiest script in the game (about twice
      `frise.io`), and `plaine.io`/`arbre.io` execute **only when the view changes** — scene
      assets carry per-scene script, not just pixels.
      To finish: find the trigger. The list of what it is **not** is now long enough to be
      the finding (FINDINGS 4.17b). Zero `encont.io` samples in: idle, walking, turning,
      approaching an NPC (1,400-2,400 samples each); killing an NPC through the party-wipe
      screen (6,552 -- and `dead.io` turns out not to be a script at all, T48); **144 steps
      across varied terrain covering twelve distinct cell values (18,863)**; and the ACTION
      menu including ORIENTATION, MAP and KILL (4,888). The terrain walk is decisive against
      movement- or cell-driven encounters.
      Candidates left, none tried: a **region change** (the six grids are not tiles, so these
      are scripted -- T11g3e is the same experiment), entering a building, and time passing.*

- [x] **T45 · What are `affobj.io`'s two conditions?**
      `affobj.io` is four near-identical ~126-byte handlers over a 2x2 matrix of two binary
      parameters (FORMATS 8.0). The 37 bytes that differ between blocks are operands to
      `0x14`/`0x1f`, so decoding expression operands would say what is being tested.
      *Method: the expression table at `0x01f2` is byte-scaled and its handlers are already
      enumerated (7.2b covers statements; expressions need the same treatment). Decode enough
      of it to render `0x14`'s condition and `0x1f`'s expression as text, then read the four
      blocks side by side — they differ only in those operands, so the parameters should fall
      out by inspection.*
      **Done when:** FORMATS names both conditions, or states which engine variables they
      test if the meaning is still unclear.
      *Met on the second branch (FORMATS 8.0b). They are **not** conditions the script tests
      — they are four variants differing by which optional statements run, on two axes:
      `0x04` (a bare `ret`, no-op) vs `0x82` (evaluate two expressions for side effects); and
      `0x52` (set frame word `es:[bp-1ah]` to `0xffff`) vs `0x54` (copy `es:[bp-3]` to
      `ss:[0c70]`, then two expressions into `ss:[0c6a]`/`[0c6c]`). That reproduces the
      ABAB/AABB split the byte diff found.
      What all four share is the substance: read entity references from **engine variables 44
      and 46** via statement `0x38` (whose handler indexes `ss:[0bf6]`, the entity block),
      branch on them, and call `vm_op_entity_clear_active` to clear the `0x40` visible bit.
      Game-level meaning of the two axes is still open; `ss:[0c6a]`/`[0c6c]` are the words
      statement `0x40` zeroes before a lookup, which is a lead.*

- [x] **T46 · Decode the expression table**
      `tools/vmi.py --listing` prints statement names but leaves every operand as raw bytes,
      so a script reads as "jump_if_zero, eval, jump_if_zero" with no sight of what is being
      tested. FORMATS 7.2b tabulated all 231 **statement** opcodes; the **expression** table
      at `0x01f2` — 112 even opcodes, byte-scaled — has never had the same treatment, and it
      is what T44 and T45 both need.
      *Method: the same one that worked for statements, and it is offline. Walk each handler
      from `ishar-listing.txt`, take operand widths from its own `lodsb`/`lodsw`, and note
      what it writes. Cross-check against the two already known: `0x00` at `seg_0000:69c7` is
      `lodsb / cbw / mov dx,ax`, a sign-extended byte immediate, and the dispatcher at
      `69ab` is `sub ax,ax / lodsb / mov di,ax / jmp cs:[di+1f2h]`, byte-scaled so opcodes
      are even.*
      **Done when:** FORMATS carries the full expression-opcode table, and `vmi.py --listing`
      renders at least immediates and variable references as text rather than hex.
      *Met (FORMATS 6.1b). All **112** expression opcodes tabulated, and the find is that
      **fifteen of them are the operator set, consecutive from 0x42 to 0x5e**: `&`, `|`, `^`,
      `^~`, `==`, `!=`, `<=`, `>=`, `<`, `>`, `+`, `-`, `/`, `%`, `*`. The six comparisons are
      told apart by their conditional jump (`jz`, `jnz`, `jle`, `jge`, `jl`, `jg`, in order)
      and the two divisions by quotient vs remainder. All fifteen named in `ishar.chani`.
      The rest load values — 38 take no inline operand, 19 a word, 14 a byte, 16 nest another
      expression, the remainder take pairs.
      `vmi.py --listing` now renders expressions infix: a statement reads
      `vm_stmt_eval e38[wordvar[48]]` instead of hex.*

- [x] **T48 · The asset size field is 24 bits, and nine assets were decoding short**
      `tools/io.py` read the `.io` header's size as a `u16`. It is 24 bits: `seg_0000:793a`
      takes the low word from `ss:[2480]` and the high byte from `ss:[2482]`, and
      `asset_decode_chunked` at `seg_0000:79a5` decodes 64 KB per round with `dec ax` per
      round (`and ax,0fh` caps the format at 1 MB). The overflow byte landed in the *mode*
      word's low half, where `>>8` discarded it, so the bug was silent on the 88 assets
      under 64 KB.
      **Done:** FORMATS 3.0 rewritten; 3.18 (`dead.io`/`auteur.io` are whole VGA pages) and
      3.19 added; FINDINGS 4.20 and the 4.19 table corrected; `tools/io.py` fixed;
      `captures/assets/` re-extracted for the nine. `dead.io`'s page matches live VRAM
      **64,000/64,000**. Corpus-wide: the `u24` size predicts the LZ stream's end for 97 of
      97 LZ assets. +470 KB of decoded content, +124 sprites.

- [~] **T47 · Read `theend.io` and `iboishar.io`**
      275 KB of decoded content that nothing explained -- the largest unread region left.
      Both grew 2 x 64 KB under T48, so nothing about them had been seen whole before.
      **Done when:** FORMATS says what the bytes are for at least one of the two, with the
      evidence being a rendered image matched against the screen or a traced consumer.
      *Half met (FORMATS 3.19). **`theend.io` is a bare 4bpp raster at a 144-byte stride**
      -- 288 pixels wide, ~992 rows, no per-image headers, starting right after the 16-byte
      asset header. Depth from the equal-nibble ratio (78.7%, against 53.6% for `logo.io`,
      59.0% for `buste.io`, 25.5% for the 8bpp `dead.io`, 6.25% random); stride from a
      row-agreement sweep that peaks at 144 (0.768 vs 0.61 either side) and returns 144 for
      `logo.io` as the control. Rendered, it is a colonnade with figures -- an ending scene.
      It is also the only asset in the corpus with **no palette record at all**.
      Two things are not met. The palette is unknown -- `geren.io`'s sixteen bank groups were
      tried and none is right -- so no render can be matched against the screen yet. And
      `iboishar.io` resisted everything: no sprite chain, no VGA page, and **no stride at
      all** (best 0.43 at 256 with every neighbour within 0.02), despite three palette
      records at 62,445 / 77,192 / 78,295. FORMATS 3.19b records it as still unread.
      To finish: trace the consumer rather than guess. Both files are reachable in game --
      `theend` needs the ending, `iboishar` is presumably the in-game Ishar screen -- so
      breakpoint each load and follow which routine reads the decoded buffer, and with what
      stride. That also hands over the palette.*

- [ ] **T50 · Regenerate the corpus classification after the size fix**
      FORMATS 3.6's table (63 sprites / 4 palettes / 18 text / 13 data) and
      `.ish/file-classification.json` were generated with the truncated decoder, and the
      script that made them is not in `tools/`. Two rows are known wrong -- `auteur.io` and
      `dead.io` are filed as "data" and are whole VGA pages -- and four sprite counts came
      from short decodes.
      **Done when:** the generator lives in `tools/`, 3.6's table is regenerated, and it
      agrees with FINDINGS 4.19 asset for asset.

- [ ] **T11g3c · Is the party's position structurally part of the level block?**
      The party's row and column are the two bytes immediately after the resident map grid
      -- grid at linear `0x129d0`, 4,860 bytes, row byte at `0x13ccc`, coinciding exactly
      (FINDINGS 6.7b). One observation, one level, one session. If it is structural, a
      rewrite can model a level as `grid[4860] + row + col + ...`; if it is allocation luck,
      the address must be found again per session and nothing follows from it.
      *Method: walk into a second region so another `cont*.fic` loads, find that grid in
      memory the same way (a 64-byte probe from the file), and check whether the bytes that
      move under the arrow keys are again at grid_end and grid_end+1. Dump the 64 bytes
      after the grid in both cases and diff the shape.*
      **Done when:** FINDINGS says whether the offset holds across two levels, and if it
      does, what else the bytes after the grid hold.

- [~] **T11g3d · Tie a map cell value to the sprite it draws**
      Twelve walkable values turned up in 38 cells and `cont1` scatters ~50 low values over
      ~1,275 cells, ~25 each -- the shape of per-cell scenery markers over a base of `0x00`
      (FINDINGS 6.7b). No value is tied to a specific sprite, so a rewrite can walk the world
      but cannot draw it.
      *Method: `tools/t11g3-look.py` walks a line and writes the viewport at each cell named
      by that cell's grid value. Two cells sharing a value should show the same object; two
      differing should not. Start with the values that recur -- `0x03`-`0x06` and
      `0x13`-`0x1b` -- and compare the captures pairwise before trying to name anything.*
      **Done when:** at least three cell values are matched to a named sprite from a scene
      asset, with the two captures that establish each.
      *The path from the map read to a decision is now readable end to end, offline
      (FINDINGS 4.19e). `lacustre.io` 1190 reads `global[0x0080 + index]` and **stores it
      into frame variable 33** -- statement `0x1e` turns out to be evaluate-then-STORE,
      dispatching the byte after the expression through the store table, which nothing had
      recorded. At 1410 a `0x2f` switch dispatches on that variable with bias -54, so on
      **cell values 0x36..0x39** -- exactly the run in `cont1.fic` at column 17, rows 25-33.
      Arms are shared (`0x37` and `0x38` go to the same place), and the first thing an arm
      does is test global `+0x137E`, which is the byte after the party's row and column and
      **reads 2 while ORIENTATION reports East** -- the first handle on the facing the arrow
      keys do not change.
      So there is no cell-to-sprite table: a cell value indexes a hand-written switch. Not
      met -- the arms were not followed as far as a draw. The shape to look for in any scene
      asset is `26 80 00` followed within a few statements by `2f` on the variable it was
      stored into.*
      *Not met, and the reason is the finding (FINDINGS 4.19d). **The capture method does not
      work**: the viewport holds many cells at once, so two cells with the same value ahead
      gave completely different pictures. Tracing the consumer instead: a `MEMORY_READ` on a
      grid cell fires, reproducibly on two cells, **three times at `seg_0000:7153` -- inside
      the VM expression evaluator**, and nowhere else. No native routine reads the map.
      **So there is no cell-to-sprite table to extract; the mapping is bytecode.** A rewrite
      must port the scene scripts or reimplement their behaviour by observation.
      What that bought: the map is a VM global. Against the base at `ss:[0bf6]` (`0x12950`,
      the same in two sessions) the grid is `+0x0080`, party row/col `+0x137C`/`+0x137D` and
      the region id `+0x3EAC` -- so 6.7b's "the position bytes sit at grid_end" is not luck,
      they are the next fields of one structure. FORMATS 3.12 carries the layout.
      Also corrected: `0x0A` blocked a move at `(14,29)` and allowed one at `(11,40)`, so
      **blocking is not a function of the cell value alone** -- which follows, since a script
      decides and can consult anything.
      Answered on the second pass. Widening to **95 and 51 genuine stops** on two watched
      cells makes one site dominant in both: `seg_0000:7153` with the script PC in
      **`lacustre.io` at 1190-1200** (36 and 23 hits, scattered singletons elsewhere).
      `lacustre.io` is the *lakeside* scene script and the party is by the lake, so the
      reader is the scene script for the terrain underfoot -- not `gerdep.io`, which was the
      favourite on etymology and call count.
      The statement decodes completely and gives the VM's **array machinery** (FORMATS 7.2h):
      expression `0x26` is an indexed global byte load, `vm_index_byte` reads a descriptor
      from the bytes *below* the data (dimension count at `base-1`, stride words below
      `base-2`), and `0x40`/`0x36`/`0x38`/`0x3a` are push/pop/sequence/end on an expression
      stack. The map is `26 80 00` -- base `0x0080`, dimension count 1, **stride 90 read
      live** -- so `map[54][90]`, accessed `map[row][col]`. The stride the game stores is the
      one the grid geometry independently requires, which is the check.
      Left: the Done-when as literally written (three values matched to named sprites) stays
      unmet and is now known to be the wrong question -- there is no table. The useful
      successor is T11g3h.*

- [~] **T11g3e · How does the party change region?**
      The six grids are self-contained -- no edge continues into another, each closed by its
      own `0xCE` outline (FORMATS 3.12) -- so moving between them is scripted. `telep.io`
      (*téléportation*, 2,016 bytes, script, no entry set) is the obvious suspect and has
      never been seen to run.
      *The premise was wrong and the correction is the finding (FINDINGS 4.19b). **A region
      is a named sub-area of a grid, not a grid file.** Walking east from the start changes
      the panel caption FRAGONIR -> ANGARAHN with the same `cont1.fic` resident and
      byte-identical. Six grids, **twenty-one regions**, and the names are bytecode in
      `frise.io` and `gerdep.io` -- a 17-byte if/else-if ladder whose word operand steps down
      by `0x11` per entry. The last two are `ISHAR` and `L'OCEAN`, so the fortress and the sea
      are both regions, which is what the impassable `0xCC`/`0xCD` blobs are.
      Also corrected: the starting region is **FRAGONIR**, not "Dragonia" -- that name came
      off a 640px screenshot and had been repeated in eleven places.
      Still open: what selects the region. Not the cell value -- the party stands on `0x00`
      in both. The name lands in a DGROUP buffer at `ss:[0x0902]`, so the writer of that
      buffer is the next thing to find, and `tools/t11g3e-region.py` already narrows the
      candidate bytes.*
      *Method: walk to a region exit and poll for a second `cont*.fic` appearing in memory,
      the way `cont1.fic` was located (a 64-byte probe from each file over a 640 KB dump).
      The moment it loads, poll `vm_run` for which scripts execute -- that is also the run
      that would finally give `telep.io` an entry set (T37e) and might catch `encont.io`
      (T44).*
      **Done when:** FINDINGS says what triggers a region change and which grid replaces
      which, with the second grid located in memory.

- [x] **T11g3f · What selects the region?**
      Twenty-one named regions live inside six grids and the panel caption tracks the party
      (FINDINGS 4.19b), but nothing yet says how a cell maps to a region. It is not the cell
      value: the party stands on `0x00` in both FRAGONIR and ANGARAHN. The name string lands
      at `ss:[0x0902]`, eight bytes, with a copy at `ss:[0x0805]`.
      *Method: `tools/t11g3e-region.py` samples DGROUP at several cells per region and keeps
      the bytes constant within and differing between; run it over three or four regions
      instead of two and the region **id** should fall out as a small integer. Then find what
      writes it -- a region map alongside the grid, or a bounding box per region.*
      **Done when:** FINDINGS says how a `(grid, row, col)` maps to one of the 21 names, and
      a prediction made from it matches the caption at a cell not used to derive it.
      *Half met (FINDINGS 4.19b, FORMATS 7.2g). **The region id is VM global byte `0x3EAC`**,
      read at `es:[ss:[0bf6] + 0x3eac]` -- 0 FRAGONIR, 1 ANGARAHN, 2 OSGHIROD, indexing the
      21 names. Found by decoding the caption's **switch**: statement `0x2f` turned out to be
      a jump table (expression, case count, bias word, one signed displacement per case), and
      its selector expression `1e ac 3e` is `vm_op_load_byte_global 0x3eac`, so the operand
      names the variable outright. `tools/region.py` reads it and is immune to the scratch
      buffer that fooled the caption-scraping version.
      Not met: what **writes** `0x3eac` from the party's coordinates. It is not the cell value
      -- the FRAGONIR/ANGARAHN boundary is between columns 45 and 46 at two different rows
      with `0x00` on both sides. Mapping it by walking is impractical because the world is
      gated: three attempts to leave the opening area each reset the party to its start cell.
      Cheapest next lead: **ACTION -> ORIENTATION reports the region in the facing direction**
      (`E : LOTHARIA` from ANGARAHN), so region adjacency can be read without walking there.*
      *Met. A `MEMORY_WRITE` breakpoint on the region byte catches the change at `(10,46)`
      east and `(10,45)` west, with `IP` inside `vm_run`'s fetch loop -- so **a script writes
      it** -- and `DS:SI` names **`gerdep.io` @7243**. Decoded with the operator table it is
      `if (column < 46) && (region == 1)`, which is precisely the boundary measured at rows
      10, 11 and 12 before the bytecode was read. The next condition along is
      `(row == 25) && (column == 60) && (region == 1)` -- one cell, not an area.
      **So there is no formula and no table**: region membership is a list of hand-written
      coordinate comparisons in bytecode (FINDINGS 6.7b).*

- [!] **T11g3g · Get inside a building**
      Rare high cell values are individual buildings -- `0xF0` and `0xEB` at the village in
      `cont1` each put a wooden door on screen and refuse entry (FINDINGS 4.19b). Clicking
      the door does nothing and starts no script (4,323 samples). Entry is the last untried
      `encont.io` trigger and the only route to the interior assets (`intmais.io` 31 sprites,
      `itaverne.io`, `inville.io`).
      *Method: the ACTION menu has **PICK LOCK**; try it facing the door. If that fails, the
      party may need to be facing the cell -- **ORIENTATION** is the verb that sets facing,
      and the arrow keys do not (4.17b). Poll `vm_run` throughout.*
      **Done when:** FINDINGS records how a building is entered, with the interior on screen.
      *[!] Parked after four failed approaches (FINDINGS 4.19c): walking into the cell,
      clicking the door, ACTION -> PICK LOCK then clicking the door, and the panel's compass
      buttons. None opens it and none starts a script. Worse, **the party then cannot move in
      any direction at `(17,53)`**, including the way it came, while the ACTION menu still
      opens -- twice now, and once it preceded the UI degrading. Unresolved whether that is a
      script gate, an un-cleared modal state, or this harness.
      Two things learned on the way. **ACTION verbs are modal**: PICK LOCK arms the pointer
      and blocks the arrow keys until used or cancelled, the same two-step as ATTACK -- a
      rewrite needs a pending-verb state. And **ORIENTATION is a readout, not a control**: it
      names the region in the facing direction, which corrects what 4.17b first said about it.
      Next: restart clean, reach the village without any menu interaction, and try walking
      into the door from each of the four sides before touching a verb.*

- [ ] **T11g3h · Read what a scene script does with a map cell**
      The access is located: `lacustre.io` at 1190 reads `map[row][col]` via expression
      `0x26` (FORMATS 7.2h), and it is the scene script for the terrain underfoot that does
      it. What it does with the value -- which sprite, at which position, at which scale --
      is the last step between "can walk the world" and "can draw it".
      *Method: `tools/vmi.py --listing` drifts around 1190 (the statement at 1190 renders as
      three overlapping decodes), so fix the traversal there first -- the raw bytes
      `1e 38 12 18 40 12 19 26 80 00` are a clean 10-byte statement and a correct stepper
      must produce exactly that. Then read forward: the branch immediately after the load is
      what turns a cell value into a decision, and `0x45` (`vm_op_load_asset`) or a sprite
      draw should appear within a few statements.*
      **Done when:** FINDINGS shows, for one cell value, the bytecode path from the map read
      to the draw, and says what is drawn.

- [ ] **T51 · Close the largest unexplained asset regions**
      **Largely answered by T53 (FINDINGS 4.15b).** Most of this was sprites nobody walked
      to, not an unknown format: `tools/ioscan.py` walks only the highest-scoring chain and
      assets hold several. `tools/chains.py` walks them all and took FILES.md from 47.9% to
      **61.8%** named. What remains is the files that did not move -- `marchand.io` is still
      3.8%, and its chain really does end with a different record type.
      `FILES.md` measures what is left: **61.8% of the 2,370,078 decoded asset bytes have a
      named structure**, and the shortfall is concentrated, not spread. By bytes unexplained,
      after multi-chain walking: `theend.io` 142,707 · `stage.io` 70,643 · `iboishar.io` 67,905 · `preson.io` 47,548 · `saub.io` 45,236 · `marchand.io` 39,344 · `frise.io` 35,309 · `ville.io` 26,304 · `scave.io` 24,926 · `samb.io` 21,592.
      **The framing "the sprite chain stops early" is wrong and the check that shows it is
      one command.** `marchand.io`'s chain ends at 7402 with 32,479 bytes left. What sits
      there is `01 04 00 00 0b 00 01 08 1e 00 09 00 16 00 ff 00 7d 00 dd dd 34 34 34 34` --
      a would-be mode byte of `0x01`, which is **odd**, and every expression-table opcode and
      every sprite mode in this format is even. Loosening `rec()` would be chasing the wrong
      thing: this is not a rejected sprite header, it is **a different record type**.
      So the real question is: what is the second structure in an asset, after the sprite
      chain? Ten files hold 686 KB of the 1,236 KB unexplained, and if they share one
      structure it is the single biggest win left in the corpus.
      *Method: collect the bytes at the point every chain stops, across all ten, and look for
      a common shape before theorising about any one of them -- `tools/anatomy.py <asset>`
      prints the stop offset. Then trace the consumer (`find-consumer`): break on a read of
      that offset while the asset is on screen and see which routine walks it. Reading the
      bytes has already failed once here; the machine has not been asked.*
      **Done when:** `tools/anatomy.py --all` reports over 65% of bytes named, or FINDINGS
      says why a named region is not reachable for the files that resist.

- [ ] **T52 · Is the `s*` cluster the game's audio?**
      `samb.io`, `saub.io`, `scave.io`, `scomb.io` and `preson.io` are five of the thirteen
      unclassified assets and 155 KB between them. Ishar's filenames are French
      abbreviations -- `souris` mouse, `frise` frieze, `gerdep` *gestion deplacement*,
      `affobj` *affichage objet*, `encont` *rencontre* -- and on that reading `s` is *son*:
      *son ambiance*, *son cave*, *son combat*, *presentation son*. Nothing about the game's
      audio has ever been looked at.
      *Method: the etymology is a lead, not evidence. Arm a breakpoint on the AdLib writer
      (`adlib_sequencer`, `seg_0000:93a6`, which writes OPL registers via port 0x389) and
      see which buffer `cs:[91a2]` points into when music plays, then find that buffer's
      source. `samb.io` already has an entry set and runs during play, so it is script, not
      a raw bank -- which the hypothesis has to account for.*
      **Done when:** FINDINGS says what at least one `s*` asset holds, with the evidence
      being a traced consumer rather than the filename.

## Rendering the viewport (the rewrite's stated goal)

- [ ] **T53 · Measure the static UI layout**
      The chrome's art is done -- `frise.io` is the whole panel, action bar and life bars at
      three palette bases, `buste.io` the portraits, one verified byte-for-byte against VRAM
      (FINDINGS 4.15). **Placement is the only gap**, and T40d/e/f failed three times to
      derive it: positions are not in the file, they are fields of 38-byte runtime instances
      whose panel entries were never found.
      For a rewrite this does not need deriving. The UI is static and never moves.
      **Eight positions are already recorded** and this task should not re-measure them:
      FORMATS 3.17 lists `(0,147)` -- the leftmost portrait, confirmed pixel-for-pixel
      against VRAM -- plus `(0,139)`, `(24,157)`, `(0,175)`, `(14,199)`, `(31,152)`,
      `(19,157)`, `(24,152)`, all polled from `ss:[0c2c]`/`[0c2e]` during a live redraw.
      What is missing is which **sprite** belongs at each of the seven unconfirmed ones.
      *Method: decode `frise.io`'s and `buste.io`'s sprites, and for each of the seven
      positions test which sprite's pixels match the framebuffer there at the known palette
      base -- the T36 technique, which matched the panel immediately even though it never
      matched the viewport. Then sweep for positions the redraw poll missed.*
      **Done when:** FORMATS carries an (asset, sprite offset, x, y, palette base) table for
      every chrome sprite, and rendering from it reproduces the panel against a captured
      frame.

- [!] **T54 · The viewport projection: what sets the two per-row steps**
      `viewport_row_loop` advances source and destination by two independent per-row deltas
      read from `cs:[002c]` and `cs:[002e]` -- sampled live at 15 and 321 while walking in
      Fragonir (FORMATS 3.13d). A destination step of 321 on a 320-wide buffer shears every
      row one pixel sideways, which is the perspective; the source step sets how fast the
      sprite is consumed, which is the size. **Nothing knows what computes either from an
      object's distance**, and that is the maths a rewrite has to reproduce.
      *Method: the party's cell is readable and so are the instances (`explore-world`), so
      distance to a drawn object is known. Poll `cs:[002c]`/`[002e]` while stepping toward a
      fixed object -- a tree in Fragonir -- and tabulate the pair against distance. A
      reciprocal in the source step would be the classic 1/z. Then find the writer of those
      two words and read it.*
      **Done when:** FORMATS gives the two steps as a function of distance, and a predicted
      pair matches a polled one at a distance not used to derive it.
      *[!] **Premise dead, and the correction is worth more than the task was.** The two
      words are not a projection. An execution breakpoint at `seg_0e97:05f4` -- the row tail
      both viewport loops share -- gives `dst - DX = 320` on **30 of 30** stops, with `DI`
      advancing exactly 320 per row and `SI` exactly the source stride. So `cs:[002e]` is
      `320 + pixels drawn`, cancelling the inner loop's walk, and `cs:[002c]` is
      `source stride - ceil(pixels/2)`. **The blit is 1:1; nothing scales or shears.**
      FORMATS 3.13d's reading -- 321 on a 320-wide buffer as a one-pixel shear, "which is
      where the perspective comes from" -- is struck. The sampled values were right; the
      interpretation was wrong. Also: they are CS-relative inside `seg_0e97`, so the segment
      is `load + 0x0e97`; read in the load segment they give 34 and 9982, which looks
      plausible and is wrong.
      A pre-flight note for whoever reads this: 3.13d's **Verified by** line covered how the
      routines were *found*, not how the two values were *interpreted*. The number was
      measured and the sentence around it was not.
      Superseded by T54b -- there is no projection to find.*

- [x] **T55 · Which asset does a viewport object come from?**
      Instances carry a viewport object's X/Y (FORMATS 3.17) and the scene scripts read the
      map (FINDINGS 4.19d), but nothing connects a drawn object to the sprite it is drawn
      from -- and the framebuffer cannot answer it, because viewport pixels are sheared and
      row-skipped and never appear verbatim (4.15).
      *Method: break in `viewport_expand_4bpp` (`seg_0e97:0644`) and read DS:SI at the stop
      -- that is the source pixels, so the pointer identifies the asset and the offset
      within it, the same attribution `tools/t44-when.py` does for script PCs. Walk toward a
      lone tree and the same source should recur at growing sizes.*
      **Done when:** FINDINGS names the asset and sprite offset behind one identified
      viewport object, with the source pointer that establishes it.
      *Met, with four (FINDINGS 4.15c). The viewport's backdrop is **`fond.io`** -- sprites
      at 1366 (64x43), 2750 (64x85), 5478 (48x69) and 7142 (96x63), read from `DS:SI` at
      the row step and matched against the decoded assets.
      **The breakpoint had to move first.** `seg_0e97:05c0` -- named `viewport_row_loop` in
      FORMATS 3.13d -- draws the **panel**: 9 of 9 sampled rows came from `frise.io` at
      x=272. The 3D view is drawn by the opaque expander at `0644`, whose row step is
      `0660`. Three loops in `seg_0e97` share the identical row-step idiom, so identifying
      one of them by watching back-buffer writes never established which served the
      viewport. `viewport_row_step_opaque` is annotated.*

- [ ] **T54b · Which sprite of the ladder is drawn at which distance?**
      The viewport blits 1:1 (T54), so an object's apparent size is the size of the sprite
      chosen. `arbre.io` holds fifteen sprites graded 16x15 through 144x83 -- a ladder, not
      fifteen different trees. What picks a rung is the real projection, and it is far less
      work for a rewrite than perspective maths would have been.
      *Method: break at `viewport_row_step` (`seg_0e97:05f4`) and record `DX` (pixels per
      row), `BP` (rows) and `SI` for every object in a frame -- that identifies the sprite
      being drawn by its dimensions. Walk one step toward a lone tree in Fragonir and see
      which rung replaces which. The party's cell is readable (`tools/region.py`), so the
      distance is known; tabulate rung against distance. `tools/t54-rowloop.py` already
      collects the registers.*
      **Done when:** FINDINGS gives the sprite chosen at each distance for one object, and
      a prediction matches at a distance not used to derive it.
      *Partial. The set of sprites drawn **does** change with the party's cell: at `(10,40)`
      the view is built from `fond.io` @5478, @7142, @1366 and @2750; three steps north at
      `(12,40)` it is almost entirely @1366. So sprite choice tracks position, as the
      1:1-blit model requires.
      Not met: pinning one object to one rung. Several objects are in view at once and the
      probe reports them together, so "which sprite for this tree at this distance" cannot
      be read off yet.
      Next: the instances carry each drawable's viewport X/Y (FORMATS 3.17), so correlate a
      row's `DI` -- which gives the screen position directly -- against the instance list,
      and follow a single object across steps instead of aggregating the frame.*
      *Second pass: objects can now be separated (`tools/t54b-objects.py` -- `BP` counts
      rows remaining, so a run of decreasing `BP` is one object and its first `DI` is the
      origin). That produced a finding about the **backdrop** rather than about the ladder:
      `fond.io` @1366 is the ground band, **one 64x43 sprite tiled every 64 pixels** at
      y=83 starting at x=-17, and @2750 is the sky at (96,0) (FINDINGS 4.15c).
      **Pre-flight failure worth keeping, and then reversed in the same session:** the
      pre-flight recorded that `arbre.io` had **never been observed drawn** -- true of every
      probe tried up to that point, and the size ladder was therefore a fact about the
      file's sprite dimensions rather than about how the game uses them. Two probes later it
      *was* caught drawn, at `(13,28)`, so that note is superseded by the paragraph below.
      Unblocked, and the pre-flight note above is now wrong: **`arbre.io` IS drawn.** The
      masked expander (loop at `0568`, row step `059a`) draws everything transparent --
      `main.io`'s font glyphs, `plaine.io`'s scenery and `arbre.io`'s trees -- and one frame
      at `(13,28)` caught **two rungs of the ladder at once**: @25490 (16x27) at (247,61)
      and @25714 (16x15) at (256,66), plus the 144x83 foreground branch @12906. Different
      rungs, different heights, same frame -- the ladder in use (FINDINGS 4.15c).
      Still not met: which rung at which distance. That needs the **same object** across two
      party positions, and the capture is not reliable frame to frame -- the breakpoint slows
      the machine so far that a window catches only part of a redraw. One run at `(13,28)`
      gave 14 objects; the same run length at `(17,28)` and `(14,28)` gave one and two.
      *That next step was tried and it does not work, which is itself the finding. The
      breakpoint-free inventory (`tools/onscreen.py`) finds **no `arbre.io` sprite on screen
      at all** -- not at `(11,28)`, `(13,28)` or `(15,28)`, the same cell where the
      breakpoint had just watched three being drawn, and not along column 42 either; a
      shorter probe for narrow ragged sprites changed nothing.
      **The two instruments see different things.** The row-step breakpoint sees everything
      *drawn*; `onscreen.py` sees only what *survives* to the final frame, and an `arbre.io`
      tree is drawn and then covered. So 4.15d's seven 100% matches are the unoccluded
      sprites, not an inventory of the frame.
      Three approaches tried, stopping here. What would actually work: make the breakpoint
      capture whole frames instead of windows -- arm it, let the game redraw once with no
      input, and collect until `BP`-runs stop arriving, rather than driving the party and
      sampling for a fixed time. That removes the partial-redraw problem without giving up
      the only instrument that can see an overdrawn sprite.*
      *Whole-frame capture built (`tools/t54b-frames.py`) and it works: a frame is now whole
      or empty, and an empty one correctly reports a refused move. It caught the ladder in
      use **on a character** -- `bormin.io` at three distances, @2152 16x29, @1424 32x45,
      @3714 48x31 (FINDINGS 4.15f).
      **Still not met, and now for a better reason.** The acceptance criterion is a
      prediction holding at a distance not used to derive it, and the prediction failed.
      `bormin.io`'s sprites sort by height 7, 12, 15, 19, 29, 31, 35, 39, 45, 68; from 16x29
      at three cells and 32x45 at two, the rung at one cell should be 32x68. It is 48x31 --
      wider and shorter -- verified against video memory, so not a mis-capture.
      So **the ladder is not a monotonic size sequence.** Two readings, neither checked: the
      sprites may be *parts* of a figure rather than whole ones per range (48x31 covers the
      upper body of a figure visibly ~60px tall, so something draws the rest), or they may be
      poses chosen by more than range.
      Next: settle that first, and it is cheap. Stand adjacent and run `tools/onscreen.py`
      over every asset, not just `bormin.io` -- if a second sprite is on screen below @3714,
      the figure is composed of parts and "which rung" is the wrong question.*
      *[!] **The question is wrong, which is the answer (FINDINGS 4.15g).** A second sprite
      is there: adjacent to the NPC, `bormin.io` @3714 (48x31 at (103,60), 100% of 779
      opaque pixels) sits on top of @2770 (48x39 at (104,91), 92.8% of 1024), contiguous and
      one pixel apart in x, together 48x70 -- the figure as it appears. So `bormin.io`'s
      twelve sprites are **body parts at several ranges, not twelve whole figures**, and the
      prediction that failed in 4.15f failed because sorting them by height sorted a mixture
      of halves and wholes.
      This task is therefore closed as mis-framed rather than met. Its successor is T54d:
      per range, the set of parts and their relative offsets.
      One instrument note: the first probe for a second part stepped its search by two
      pixels and @2770's origin has an odd y, so it reported 50.9% and looked like noise. A
      grid that skips the answer reports its absence.*

- [x] **T53b · Bind the polled chrome positions to their sprites**
      T53 confirmed two sprites; seven polled positions had no sprite attached.
      **Done when:** every chrome sprite has (asset, offset, x, y, base) and the table
      reproduces the panel against a captured frame.
      *Met (FORMATS 3.17b). Six sprites placed, four of them at **100%** of their opaque
      pixels against live VRAM. The finding that matters for a rewrite: **the layout is a
      64-pixel grid** -- the ACTION/ATTACK bar and the LIFE bar are each ONE sprite drawn
      five times at x = 0, 64, 128, 192, 256, so the seven "positions" polled in T40 were
      repeats of two sprites, not seven different ones.
      Every score below 100% is explained rather than tolerated: the LIFE bar at x=0 is
      75.7% because the stored sprite is the *empty* bar and character 1's is filled, which
      proves the fill is drawn over it; the panel is 85.8% because the caption, needle and
      DISK button composite on top.*

- [ ] **T53c · Where does the empty-slot medallion come from?**
      The four unoccupied portrait slots show a grey medallion whose pixels are in **no
      asset**: searched across all 106 files, as 8bpp raw and as 4bpp at every palette base
      that could contain the run, zero hits. The same probe found the portrait, both bars
      and the panel in the same frame, so the instrument is sound (FORMATS 3.17b).
      *Method: it is drawn by something, so trace the drawer rather than search for the
      bytes. Break in `sprite_blit_ingame` (`seg_0e97:038b`) during a panel redraw and read
      DS:SI at each stop -- that is the source pointer, so it names where the pixels come
      from even if they are built at runtime. If they are generated rather than stored, that
      is the answer and a rewrite can draw the medallion any way it likes.*
      **Done when:** FINDINGS says where the medallion's pixels come from.

- [x] **T56 · Where is the starting NPC's sprite?**
      Two cells north of the start a man stands in the viewport, talks when walked into, and
      can be attacked (FINDINGS 4.17). His pixels are in **no asset**: a sweep over every
      sprite of all 98 files at every palette base, verified whole-sprite against video
      memory, finds seven other things in that frame at 100% and not him (4.15d).
      `bormin.io` -- whose name reads like a character -- is not on screen either, 0 of 12.
      *Method: he is drawn by something. The row-step breakpoints that identified `fond.io`
      and `frise.io` (T55) never caught him, so find the path first: break on writes to the
      back buffer inside his bounding box -- roughly x 115..150, y 55..110 with the party
      two cells south -- with a control breakpoint on never-written memory to subtract
      phantom stops, and read the routine and `DS:SI` at each hit. That is the technique
      that found the viewport routines originally.*
      **Done when:** FINDINGS names the asset and offset his pixels come from, or shows
      what transforms them.
      *Not the NPC yet, but the method now works and found the drawing paths (FINDINGS
      4.15e). Watching writes to one back-buffer pixel with a control on never-written
      memory gives **three** real writers of a viewport pixel, all with zero control hits:
      `seg_0e97:06d5` (fill), `0657` (opaque expander), `0597` (masked expander). The
      control produced 7,709 stops across 171 sites in half the time, almost all
      `wait_loop` -- which is why it is needed.
      Attributing the masked loop's source found **the font**: `main.io` carries 16x9 glyph
      sprites drawn 7 pixels apart, six of them confirmed. And `plaine.io` @32264 is a
      16x7 scenery element tiled every 24 pixels.
      To finish: run `tools/t56-writer.py` on a pixel inside the **NPC** rather than a
      tree, then attribute the source at whichever of the three sites fires.*
      *Met, by a different route (FINDINGS 4.15f). The pixel probe was not needed: capturing
      **whole frames** instead of fixed windows -- one key, then collect until no stop has
      arrived for 2.5s -- caught him directly. **The NPC is `bormin.io`**, at three offsets
      for three distances: @2152 (16x29) at ~3 cells, @1424 (32x45) at ~2, @3714 (48x31)
      adjacent. The last is confirmed **100% of 779 opaque pixels** against video memory by
      `tools/onscreen.py`.
      That also corrects 4.15d's "`bormin.io` is not on screen, 0 of 12 sprites" -- true of
      the frame measured, where the party stood elsewhere, and wrong as a claim about the
      asset. The lesson is the one already in this file: a routine that fires is not a
      routine that fires when you care, and the same goes for a sprite.*

- [x] **T56b · Does an NPC block its cell?**
      `0x0A` refuses a move at `(15,29)` and permits one at `(11,40)` -- the anomaly behind
      "blocking is not a function of the cell value" (FINDINGS 6.7b). The starting NPC
      stands about where `(15,29)` is, which would explain it: the cell is walkable and the
      *occupant* blocks.
      *Method: kill or recruit the NPC -- ACTION offers both -- and retry the move onto
      `(15,29)`. If it succeeds afterwards, the block was the NPC. Cheap, and it also gives
      a second data point on what RECRUIT does.*
      **Done when:** FINDINGS says whether occupancy blocks movement independently of the
      cell value.
      *Met, and without needing to kill anyone (FINDINGS 4.15i). Cell `(13,29)` -- value
      `0x02` throughout -- was refused, then walked onto, then refused again within a few
      minutes. **Occupancy blocks; the cell value does not change.** That settles 6.7b's
      anomaly: `0x0A` refused a move in one place and allowed it in another because
      something was standing on one of them. A rewrite needs an occupancy layer over the
      terrain grid.
      The NPC also **wanders continuously**, which is why he is a useless measurement target
      -- T54c and T54d have both now failed on the distance changing mid-measurement.*

- [ ] **T57 · Give the 17 pre-Evidence sections an evidence line**
      `tools/checkdocs.py` now fails any numbered section in FINDINGS or FORMATS with no
      **Evidence:** / **Verified by:** / **Status** line. Seventeen predate that discipline
      and are listed in `EVIDENCE_DEBT` in that script so the gate stays green and the debt
      stays countable: FINDINGS 1.2, 1.3, 2.2 and FORMATS 1.1-1.4, 3.1, 8.1, 8.2, 9.1-9.3,
      9.6, 10.2, 10.3, 10.5.
      They are not all the same job. Some are placeholders that should say **Status: nothing
      established** (FINDINGS 1.2 Combat, 1.3 Magic). Some rest on work that *was* done and
      never cited -- FORMATS 1.1-1.4 are the unpacked-image layout, whose gate is
      `tools/verify-unpack.py`. Some may rest on nothing, and saying so is the result.
      *Method: one section at a time, and **do not invent the line**. If the evidence cannot
      be named, write `Status: not verified` and, where it matters, file the measurement as
      its own task. Remove each entry from `EVIDENCE_DEBT` as it is done, so the count only
      goes down.*
      **Done when:** `EVIDENCE_DEBT` is empty, or every remaining entry carries a
      `Status: not verified` line and a task for the measurement.

- [ ] **T54d · The part list per range**
      T54b is mis-framed: a character is drawn from **stacked parts**, not one sprite per
      distance (FINDINGS 4.15g). Adjacent, the starting NPC is `bormin.io` @3714 over @2770
      at `dx +1, dy +31`; at three cells he is a single 16x29 with nothing under it. So what
      a rewrite needs is, per range, the parts and their relative offsets -- and how many
      parts there are changes with range.
      *Method: `tools/t54b-frames.py` already captures whole frames with each object's
      sprite and origin, so walk one line toward the NPC capturing at every cell and read
      the part sets straight off. Cross-check each with an exhaustive single-pixel
      `tools/onscreen.py` search -- and step by one, since @2770 was missed by a grid of
      two.*
      **Done when:** FINDINGS gives the part set and offsets for the NPC at three ranges,
      and a predicted composite matches the framebuffer at a range not used to derive it.
      *Part sets obtained for three ranges with the NPC pinned at `(15,29)` and the party
      due south, so lateral offset zero (FINDINGS 4.15i): **1 cell** = `@3714` 48x31 at
      (103,60) *and* `@2770` 48x39 at (104,91); **2 cells** = `@1424` 32x45 at (144,65);
      **3 cells** = `@2152` 16x29 at (136,72). The number of parts changes with range -- two
      adjacent, one beyond.
      Not met: the prediction. At four cells the next smaller 16-wide sprite (`@2392` 16x19)
      was expected, and the test could not be run because **the NPC walked behind the party**
      before it could retreat (4.15i).
      **Blocked on the same thing as T54c: a target that holds still.** Do not retry either
      against an NPC. Pick a tree, pin its cell by finding the move it refuses, and measure
      from there -- a tree cannot walk away and its cell is then exactly known.*

- [!] **T54c · How a viewport object's screen position is computed**
      The viewport blits 1:1 and the row step gives `DI`, which *is* the destination -- so
      screen position is readable directly (FORMATS 3.13d, FINDINGS 4.15c). What is missing
      is the rule: given the party's cell and an object's cell, where does it land?
      **Done when:** an object's screen position is predicted from the party's cell and the
      object's map cell, and the prediction holds at a cell not used to derive it.
      *Filed late -- it was proposed in a reply and referenced from FINDINGS 4.15h before it
      existed here, which `tools/checkdocs.py` caught. The scar about proposing work in the
      reply rather than filing it, again.*
      *One number established (FINDINGS 4.15h): **88 pixels per lateral cell at three cells'
      distance**, from the same sprite caught at x=224 from `(12,28)` and x=136 from
      `(12,29)`. Differences are the usable form -- **absolute position cannot be read from
      one frame**, because a sprite's origin is not the object's centre and two lateral-zero
      sightings of the same NPC put its centre at 144 and 127, so every sprite carries an
      unmeasured anchor.
      Not met, and the NPC is the wrong object for it: he **moves** (`(13,29)` became blocked
      between visits), he is **occluded at distance** so the framebuffer route sees nothing
      from three cells while the breakpoint sees him drawn, and his **map cell is unknown**,
      which the criterion needs. Three attempts at more lateral points all failed on those.
      *Next: pick a fixed object whose cell can be pinned -- a tree that refuses a move,
      which identifies its cell exactly -- and measure with `tools/t54b-frames.py` at
      several lateral offsets for each of two distances. The anchor cancels in the
      differences, so the slope per distance is what comes out, and that is the projection.*
      *Tried, and a second slope came out of it: a tree (`arbre.io` @24842, 32x40) moved
      **38 pixels per lateral cell**, from x=153 at `(13,43)` to x=191 at `(13,42)`, same
      sprite and same y. With the NPC's 88 at three cells that fits
      `pixels per cell = 264 / distance` and puts the tree at 6.9 cells -- and it *is*
      farther and higher on screen. Suggestive only: the tree's distance came from its own
      slope, so confirming the law that way would be circular (FINDINGS 4.15h).
      **The blocker is object identity, not measurement.** One row closer the same tree is
      drawn from different sprites (@25490, @25714, @23962) with several trees in view, so
      nothing says which sprite is which tree. The NPC fails because he walks; the tree
      fails because it cannot be told apart from its neighbours.
      *That instrument was tried and **the premise it rested on is false** (FINDINGS 4.15h).
      Instances do not hold viewport object positions. Searching all 640 KB of conventional
      memory for the three origins drawn in one frame -- `(151,61)`, `(167,66)`, `(149,30)`
      -- as word pairs in either order gives **zero hits**, while a control in the same dump
      finds `(255,125)` four times including at the pool offset where the record sits. And
      scanning the pool for the `0x7fff` sentinel yields exactly **two** records: `main.io`'s
      two rectangles, `(255,125)` and `(319,199)`.
      FORMATS 3.17's "instances carry viewport object positions" came from the *range* of
      values in a pool scan (9..272 by 6..94, the viewport rectangle), not from matching a
      drawn position -- the same mistake as reading the palette group out of word 0. It is
      corrected there.
      **So a viewport object's screen position is computed per frame and never stored**; it
      exists only in `DI` at the row step. Three approaches to identity have now failed: the
      framebuffer (cannot see occluded distant sprites), tracking an object (the NPC walks,
      trees are indistinguishable), and the instance list (the numbers are not there).
      *[!] Tried, and it fails: the draw sequence is **not reproducible**. Two frames at the
      same cell after the same key gave **11 and 13 objects with none identical in the same
      position**; widening the quiescence window from 2.5s to 6s changed the counts and not
      the conclusion (`tools/t54c-order.py`). The cause is the instrument -- a breakpoint at
      the row step slows the machine so far that a redraw interleaves, so one key press does
      not map onto one frame.
      **Four approaches, four different reasons, so this stops.** Identity is unavailable by
      sprite (two trees share one), by tracking (the NPC walks, trees are alike), by the
      instance list (the numbers are not stored, FINDINGS 4.15h) and by draw order (not
      reproducible).
      **The answer a rewrite gets is a calibration, not a derivation**, and REBUILD says so:
      `pixels per lateral cell = 264 / distance` from the two measured slopes, with the
      per-sprite anchor calibrated by eye against a screenshot.
      If anyone wants better, the route is a **cycle-accurate trace** rather than a
      breakpoint, so that a frame is a frame -- not a fifth variation on the same probe.*

- [ ] **T58 · Is `+0x137E` the party's facing?**
      The byte after the party's row and column reads **2** while ACTION -> ORIENTATION
      reports **East** (FINDINGS 4.19e), and a scene-script switch arm tests it for equality
      with 2. One observation, so the mapping from value to compass point is unknown and
      even "it is the facing" rests on that single coincidence.
      This matters more than its size: movement is absolute N/S/E/W and nothing found so far
      *sets* facing (6.7b), so this byte is the only lead on a field the game plainly has.
      *Method: read it while changing what the compass shows. ORIENTATION is a readout, not
      a control, so find what does change facing -- walking into an NPC, entering a
      building, or a script event -- and sample the byte before and after. Failing that,
      write a value into it and see whether the compass rose and the viewport follow, which
      would settle it in one step; the party-position bytes are a copy and writing them did
      nothing, so expect that outcome and treat a no-op as informative.*
      **Half answered by T59, and the premise is now weaker:** `+0x137E` reads 2 through
      six moves in two axes (FINDINGS 6.11), so movement does not write it and it cannot be
      the facing *as movement updates it*. The remaining reading is a facing that only a
      script changes, which is worth one check and no more. What is left of this task is the
      harder half: **find where the facing actually lives**, since ORIENTATION reads one out
      and nothing found so far writes one.
      **Done when:** FINDINGS gives the value-to-direction mapping for at least two
      directions, or says the byte is not the facing.


## Understanding the mechanics (M5)

These share one method, and it is worth stating once. **The VM's global variable area is the
game's state.** The map sits at `+0x0080`, the party's row/column/facing at `+0x137C`, the
region id at `+0x3EAC` -- and character stats, money, inventory and quest flags have nowhere
else to live. Three instruments compose into a loop that answers almost any mechanic:

1. **Diff the globals across an action.** Snapshot, do one thing, snapshot, keep the bytes
   that moved. This found the party position in a single pass (`tools/t11g3-pos2.py`).
2. **Watch writes to a global and attribute `DS:SI`.** A `MEMORY_WRITE` breakpoint with the
   stop believed only when the value actually changed; the script PC names the writer. This
   found `gerdep.io` @7243 (`tools/t11g3f-writer.py`).
3. **Read that script offline.** The four dispatch tables, the switch encoding and
   evaluate-then-store are all decoded, so a rule can be read without the emulator
   (FINDINGS 4.19e).

Find the byte, find its writer, read the rule. Every task below is that loop.

- [x] **T59 · Map the global variable area**
      Everything the scripts read and write is in one flat array, and only three fields in
      it are named. A map of the rest is the foundation for every mechanic below, and it is
      cheap: most of it comes from diffing.
      *Method: snapshot the globals, perform one isolated action, snapshot again, record
      which bytes moved -- for taking a step, opening a menu, selecting a character, closing
      a panel, and waiting with no input. Bytes that move on everything are timers; bytes
      that move on exactly one action are that action's state. Then widen: the party record
      at `+0x137C` is three fields so far, so dump the 64 bytes around it and see where it
      ends.*
      **Done when:** FINDINGS carries a table of global offsets with what each holds and the
      action that revealed it, for at least twelve fields.
      **Done:** FINDINGS 6.11 names seventeen new fields, FORMATS 3.12's table carries them
      and REBUILD 8 is the reimplementer's copy. `tools/t59-globals.py`. The coordinate ones
      are exact fits of `v = +-1*row + b` across eight snapshots over four rows and four
      columns; the party's own row and column fall out of the same test, as the control.

- [x] **T60 · Find the character records**
      Five party members with names, portraits, a LIFE bar and an ACTION menu that can give
      them items and money. Their stats are somewhere in the globals, in five copies.
      *Method: T59 did the first half. The leader's name sits at `+0x472E` in the same
      8-byte form the 33-name table at `+0x1746` uses, and the record around it carries the
      party's row and column at `+0x470C`/`+0x470D`, with seven small numbers at `+0x4713`
      that look like attributes and are not yet anything but a guess. So the work is the
      stride and the fields: the party has one member, so the other four records should be
      zeros -- find them, and the stride falls out. Then confirm a field by changing it in
      game (FIRST AID on a hurt character) rather than by reading it.*
      **Done when:** FINDINGS gives the record's stride and at least four named fields, with
      one field confirmed by changing it in game and watching it move.
      **Half done (6.13).** The roster is at `+0x150C`, 8-byte name slots, confirmed by
      recruiting BORMINH and watching `+0x1514` go from zeros to his name -- the only
      zero-to-name transition in 64 KB. The sheet names the fields: name, class, race, level,
      strength, constitution, agility, intelligence.
      **Done (6.15).** There is no per-character record: the attributes are **column-major**,
      one 8-byte row per attribute with one byte per party slot, at `+0x1664`. Six rows are
      named -- class, level, strength, constitution, agility, intelligence -- with five of
      them matching BORMINH's panel exactly in the panel's own order, in a column that was
      zero before he joined.

- [ ] **T61 · What the ACTION verbs actually do**
      Ten verbs are listed (4.17b) and none is traced. RECRUIT and DISMISS build the party;
      GIVE MONEY implies a currency; PICK LOCK implies a skill check; FIRST AID implies
      healing.
      *Method: one verb per run. Arm the writer probe over the character records from T60,
      invoke the verb, and see which fields move and which script moved them. PICK LOCK is
      the most informative -- a skill check needs a stat, a difficulty and a die roll, so
      whatever it reads is the shape of every other check in the game.*
      **Done when:** FINDINGS describes what at least three verbs change, naming the script
      and the fields.

- [ ] **T62 · The murder consequence, and what gates the opening area**
      Attacking a friendly NPC resets the party to its start cell (4.17), and so does walking
      too far (6.7b) -- the same outcome from two causes, and `vm_op_consequence_event`
      (`seg_0000:4b8f`) fires at the moment of the demon frame.
      *Method: break on `vm_op_consequence_event` and read `DS:SI` to name the script and
      offset, then read that bytecode. The gate is the more useful half: if it is a condition
      on a global, that global is a quest flag, and quest state stops being a mystery.*
      **Done when:** FINDINGS names the script and the condition for at least one of the two
      resets.

- [ ] **T63 · Combat, from one swing**
      T21 has never been started and is written as though it needs a monster. It does not:
      attacking the NPC produces a complete attack sequence, and `vm_op_15` (`seg_0000:28a9`)
      already measured 7,805 calls on an attack against 0 idle.
      *Method: with the character records mapped (T60), attack and diff. Damage has to land
      in a field; whatever is read to compute it is the to-hit rule. Then read the script
      that wrote it. Do not kill the NPC -- the consequence resets the party and ends the
      measurement.*
      **Done when:** FINDINGS names the field damage is written to and the script that
      writes it.

- [!] **T64 · Does the game keep time?**
      A day/night cycle, hunger and spell regeneration would all need a clock, and nothing
      has looked. `encont.io` runs once at startup and then waits for a trigger nothing has
      produced (4.17b) -- a timer is a candidate.
      *Method: falls straight out of T59 -- the bytes that move when the party does nothing
      at all are timers. Sample the globals twice a minute apart with no input, then check
      whether any of them is what `encont.io` waits on.*
      **Done when:** FINDINGS says whether a clock exists and what advances it.
      **Reopened, and the first answer was wrong.** FINDINGS 6.12 said footsteps advanced
      the pair at `+0x438B`/`+0x438C`, from six moves in one session. In the next session, a
      fresh game, the pair advanced once and then sat still through nine moves, and jumped by
      135 across a RECRUIT with no step and no carry. So it counts something else.
      *Method: stop guessing from the outside. Break on writes to `+0x438C` with the guard
      that the watched bytes actually changed, and read `DS:SI` -- the `gerdep.io` @7243
      method from T11g3f. One stop names the script and the script says what it counts.*

- [ ] **T65 · What the step counter's high byte counts**
      `+0x438C` advances once per five steps and nothing on screen shows it (6.12). If it is
      an hour then shops, NPCs and rest all hang off it, and it is the first mechanic that
      is about the world rather than the party.
      *Method: walk 120 steps, which is 24 units if it is an hour, and watch for anything
      that changes at a boundary -- the sky in `fond.io`, an NPC that stops appearing, a
      script that fires. Then the other direction: break on writes to `+0x438C` and read
      `DS:SI` to name the script, which is the `gerdep.io` @7243 method from T11g3f.*
      **Done when:** FINDINGS says what one unit of `+0x438C` means, or that nothing
      observable keys on it.

- [ ] **T66 · The four records that shadow the party at (row+1, col+1)**
      Three places hold `(row+1, col+1)` and one holds `(row, col+1)`, all tracking the party
      exactly, roughly 0xA0 apart (6.11). Something that always sits one cell diagonally from
      the party is not an NPC, and four of them with a stride is a table.
      *Method: the stride is not clean -- 0x9E then 0xA0 then 0xA0 -- so find the record
      boundary before believing the stride. `de ff` and `63 00` sit at the same offset in
      each, which is a header to key on: scan the whole global area for it and see how many
      there are. Then recruit a second party member, which should add one if these are the
      characters.*
      **Done when:** FINDINGS says what the records are and gives their stride, or says the
      0xA0 spacing is a coincidence.

- [ ] **T67 · Is `+0x5C00`..`+0x7C00` the entity instance pool?**
      Roughly 1,300 bytes there are rewritten on every redraw (6.11), and FORMATS 7.5
      describes an instance structure reached through `ss:[0bf6]` with a position at `+0x0c`
      and `+0x0e`. If they are the same thing, the four failed attempts at object identity
      in T54 were looking in the wrong place the whole time.
      *Method: offline first -- the snapshots are already saved by `tools/t59-globals.py`.
      Take the offsets that changed on one step and look for a period. Then check whether the
      words at `+0x0c` and `+0x0e` of each candidate record are the screen positions
      `tools/onscreen.py` reports for the same frame.*
      **Done when:** FINDINGS says whether the blob is the instance pool, with the record
      stride if it is.

- [x] **T68 · Where character records actually live**
      T60 found the roster and the sheet's field names and could not find a single attribute
      value anywhere in the 64 KB global array (6.13). So there is a second store, and every
      mechanic that touches a character -- combat, FIRST AID, the team vote, levelling --
      goes through it.
      *Method: the sheet is the way in. It renders `THIEF` and `HUMAIN` into `+0x4FA8` and
      `+0x4FBA`, so break on a write to `+0x4FA8` -- with the guard that the watched bytes
      hold what you think was written -- and the caller is holding a pointer to the record.
      Read the registers at that stop rather than searching memory for values again, which
      has now failed once.*
      **Done when:** FINDINGS says where a character's attributes are stored and gives the
      record's layout for at least four fields.
      **Done (6.15), and the task's own premise was false.** It was filed on 6.13's "not in
      the global area", which came from searching a 64 KB snapshot for BORMINH's values while
      BORMINH was still an NPC. The array was at `+0x1684` in that snapshot holding ARAMIR's.
      `tools/t68-stats.py` over all 640 KB found it on the first try.

- [ ] **T69 · What a party member's vote depends on**
      Recruiting is put to a vote of the existing members and each answers OK or not (6.13).
      With one member there is one vote, so it has never been seen to fail. This is the first
      mechanic found that reads party state rather than world state.
      *Method: needs a second member, which T60 now provides, and a recruit that gets
      refused. Try recruiting a character of a different class or alignment and see whether
      an existing member votes against. Then read the script behind the panel.*
      **Done when:** FINDINGS says what a vote reads, or records a refusal and what differed.

- [ ] **T70 · How to close the inventory panel**
      Clicking a portrait opens it and it blocks all movement; Escape, a second portrait
      click, a right click and the panel's red square all failed, and recovering cost a
      restart (6.14). Until this is known the inventory -- items, weapons, what a character
      carries -- cannot be measured at all.
      *Method: it is a mouse-driven panel, so find its hit regions rather than guessing.
      Sweep the panel with `tools/mclick` one cell at a time, reading the party's position
      after each to detect the moment movement comes back. Do it on a machine that is
      expendable, since the failure mode is a restart.*
      **Done when:** `drive-ishar` carries the gesture that closes it, demonstrated twice.

- [ ] **T71 · The rows in the attribute array that nothing has moved**
      Six of the fourteen rows at `+0x1664` are named and two more read 100 for both members,
      which is what a full LIFE bar looks like (6.15). The rest changed when BORMINH joined
      and mean nothing yet.
      *Method: each row needs an action that moves exactly it. FIRST AID on a hurt character
      separates current health from maximum -- one of the two rows reading 100 should drop
      and come back. Walking into the NPC's attack does the hurting. For the rest, the sheet
      is the oracle: the panel shows five numbers, so the rows it does not show are things
      the player never sees, which makes experience, gold and encumbrance the candidates.*
      **Done when:** FINDINGS names at least three more rows, each with the action that moved
      it.

- [ ] **T72 · What the other message-asset lists hold**
      The class and race lists sit in `messagee.io` as `1e 04 <NAME> 00` records (6.15), and
      the same file holds 99 strings of which only those 21 are now placed. Spell names, item
      names and the ACTION verbs are all plausibly in there in the same form, and each list
      found is an index somebody else's byte is pointing into.
      *Method: offline. Scan every `message*.io` and `textin*.io` for the `1e 04` marker and
      group the records by their inter-record bytes -- races carry `0a 10 01`, classes carry
      `16 fe 0a XX 00`, so the trailer distinguishes one list from another.*
      **Done when:** `IDENTIFIED` carries every `1e 04` list in `messagee.io` with what each
      one is, and `FILES.md` shows them.

- [~] **T73 · `en1.fic`, the NPC table**
      Found (6.18): 32 NPC rows at offset 57, 32 columns at 197, the 33-entry cast-name
      table at 2590, and entity 0 standing exactly where the starting NPC does. What remains
      is the join and the stats.
      *Method: 2,169 bytes between offset 421 and the name table are unread, and the array
      linking an entity to its name must be in them -- look for a 32-entry array whose values
      are all under 33 and whose first entry is 28. For the attributes, `tab1.fic` is 361
      bytes nothing has opened; open it before theorising.*
      **Done when:** FINDINGS names which cast member each entity is, and says where an NPC's
      attributes come from.

- [ ] **T74 · Search the files, not the decoded files**
      `en1.fic` hid for four sessions because every corpus search ran over `decode()`d
      assets, and `.fic` files are stored raw -- the decoder turns them into noise. Any other
      raw-stored file is equally invisible to every search this project has run.
      *Method: re-run the searches that produced negatives over the **raw** bytes of every
      file in the game directory as well as the decoded ones. `tools/t68-stats.py` and the
      corpus scans in `tools/ioscan.py` are the two that matter.*
      **Done when:** a single search helper reads both forms, and the negatives recorded in
      FINDINGS have been re-run through it.


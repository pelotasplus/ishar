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
      *DONE. Both halves. Two cold boots traced through to the Dragonia outdoor frame,
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

- [!] **T29c · Attribute primitives to combat, magic and the party**
      T29 named every statement handler's signature but not its meaning. Domain verbs fire
      once per event, so the walk diff that worked for the language core cannot see them.
      *Method: `tools/t11p-diff.py` takes a call-count snapshot, runs an action, and diffs --
      it just needs the action to be a fight, a spell or a character-sheet open rather than
      walking. The attack UI is mouse-driven, so this needs either mouse input through the
      MCP or a keyboard route into combat. `seg_0000:2d94` (opcode 0x42) is the cheapest
      first target: it runs only while walking and is not an operand-skip helper.*
      **Done when:** at least ten primitives are attributed to combat, magic, inventory or
      the party, each with the action whose diff revealed it, and named in `ishar.chani`.
      *Blocked on input, not on method. One primitive attributed -- `vm_op_draw_menu`
      (opcode 0x4b, `seg_0000:3a84`) with its helper `menu_draw_item` -- confirmed across
      five triggers. The blocker: **the game uses no mouse the harness can reach.** INT 33h
      records 0 calls in 20s and the COM/PS-2 IRQ vectors are untouched BIOS stubs; only
      INT 09h and INT 08h are hooked. F1 opens the ACTION menu (FINDINGS 6.4) but its
      entries cannot be selected by arrow keys, Return, Escape or first letters, so combat,
      magic and inventory stay unreachable. `tools/t29c-action.py` and its idle baseline
      work correctly -- see T29d.*

- [!] **T29d · Find how Ishar reads the mouse**
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

- [ ] **T29e · Make the pointer usable, one way or another**
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

- [~] **T11g3 · What the map cell values mean**
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
      *BLOCKER LIKELY STALE: a stalled emulator is not a property of this task. Restart and
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

- [~] **T30 · Disassemble `main.io`**
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
      **Done when:** `tools/vmdis.py` prints a listing of `main.io` in which over 80% of the
      bytes are decoded as instructions rather than skipped, and FORMATS.md documents at
      least ten opcodes' operand layouts.
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

- [ ] **T11m2c · Check a 4bpp sprite against the framebuffer**
      4bpp sprites are opaque (FORMATS.md 3.13), established from `expand_4bpp` writing both
      nibbles with `stosw` and never testing zero. That is code-reading, not measurement, and
      the transparency rule it replaces was itself a measurement generalised too far.
      *Method: the same comparison that proved `logo.io` -- capture the framebuffer while a
      known 4bpp sprite is on screen and compare pixel for pixel, including the zeros.*
      **Done when:** one 4bpp sprite matches the framebuffer with colour 0 drawn, not keyed.

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

- [ ] **T33 · Find `affobj.io`'s entry point**
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

- [ ] **T36 · What the `b9 04` string tag is as an instruction**
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

- [ ] **T37 · The 58% problem: enter an asset's embedded script**
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

- [ ] **T19c · Why the traced run faults in the intro when a manual run does not**
      Three GDB-traced boots died at `017D:194D` (§5.0) before reaching gameplay, yet
      ordinary `run.sh` play reaches Dragonia. So the fault is a property of *how we
      drive it*, not of the intro. Bisect the difference one flag at a time: GDB
      attached vs not, breakpoint armed vs not, keys from `tools/nudge.py` vs by hand,
      dummy audio, fixed clock, `--ReloadCfgGraph`.
      **Done when:** one named difference flips the outcome across two runs each way, or
      all of them are eliminated and the fault reproduces in a plain `run.sh` session
      too — in which case §5.0 is the game/FPU issue and T08 needs a different route.

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

- [~] **T38 · Prove the `main.io` disassembly against execution**
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

- [ ] **T29c2 · Recheck T29c's "no mouse the harness can reach" blocker**
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

- [~] **T37b · Who writes `es:[bp-8]`? The general entry-point question**
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

- [~] **T37c · Catch the first `vm_run` entry for assets loaded after the menu**
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

- [!] **T37e · Entry points, now that a cheap probe exists**
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

- [ ] **T39d · The in-edges traversal cannot compute**
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

- [ ] **T39e · Why do only 70% of `0x06` targets land on an opcode?**
      231 of 256 byte values are valid statement opcodes, so ~90% of *random* targets pass
      the "is it an opcode" test. `0x06` (script call, d16 base +3) manages 61/87 = 70%,
      which is worse than chance and says those sites are being decoded at PCs that are
      themselves wrong (FORMATS 7.2d).
      **Done when:** it is established whether the sub-chance rate comes from bogus `0x06`
      sites reached down a wrong path, or from `0x06` targets being computed rather than
      immediate — with a count either way.

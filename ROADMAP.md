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

**Next up: T11q → T11p → T11r → T11m2 → T11m, then T14/T17.**

T10 and T11 are done: the container decodes, sprites are 4bpp and chain end to end, and
the palette format is confirmed against the running game's framebuffer. What remains on
graphics is a single missing association -- **which palette is live when a sprite is
drawn** -- and one unproven claim underneath it.

- **T11q** first because it costs nothing and needs no emulator: drop the ~50 chain
  records that report impossible palette groups.
- **T11p** next because it blocks everything else. The blitter we spent this work on
  fires 445 times in the launcher and intro and **zero times in the viewport**, so the
  in-game renderer is still unidentified -- and it scales sprites, which is what word 3's
  `162..165` sequence meant.
- **T11r** and **T11m2** both need T11p: proving `group * 16 + nibble`, and pairing each
  sprite with the scene palette it is actually drawn against. T11m's pixel-exact
  acceptance falls out of the same measurement.
- **T18** still lands on everything after this; bring it forward the moment a crash costs
  a second run.
- **T11m4**, **T11n**, **T11o** and **T09b** need no emulator and can fill any gap.

Then T14 and T17 -- reproducing the language screen and the first in-game screen offline
-- become the honest proof that the formats are understood.

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

- [~] **T11m · Why the colours are wrong on extracted sprites**
      **Answered, not yet proven to the acceptance bar.** The DAC is 16 sub-palettes of 16
      (FORMATS.md 3.9): 227 non-zero entries in-game, every group from 1 up starting white
      then black. So `vga_index = (word0 >> 8) * 16 + nibble`, and header word 0 -- the last
      unexplained field -- carries the group in its high byte. The full 768-byte palette is
      in the asset, 8-bit RGB: the in-game DAC matched `fond.io @ 12108` and `geren.io @ 6684`
      768/768 by exhaustive search. `tools/ioscan.py` now finds palettes by the white/black
      group signature instead of the old heuristic, which had picked 204 for `fond.io`.
      *Still open: the pixel-by-pixel confirmation the Done-when asks for. `tools/t11m-verify.py`
      searches the framebuffer for `group*16 + nibble` and found only one weak hit (32/40 opaque
      pixels of a 16x4 sprite) because the game had returned to the launcher and the blitter
      stopped firing. Redo it standing in a scene: capture with `tools/t11m-sprites.py`, then
      run the verifier immediately, before anything redraws.*
      **Done when:** `tools/ioscan.py` reproduces the emulator's framebuffer colours for one
      sprite it did not take the palette from, checked pixel by pixel.

- [ ] **T11m2 · Sprites borrow a palette from the scene, so which scene?**
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

- [~] **T11p · The viewport renderer is not the blitter we know**
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

- [ ] **T11g3 · What the map cell values mean**
      `cont*.fic` are 90x54 byte grids (FORMATS.md 3.12) with 53-91 distinct values each.
      `0x00` is open, `0xCE` the boundary, `0xCC`/`0xCD` outside; the rest are terrain and
      object types and are undecoded. This is the world's content -- where towns, dungeons
      and encounters are -- so it feeds T23 (quests) and any rewrite's map loader.
      *Method: the party's position is in memory while the game runs; walk a known route,
      read the coordinates, and index the grid to see which value the party is standing on.
      Cross-reference cells against the assets a scene loads.*
      **Done when:** at least eight cell values are identified in FINDINGS.md, each with the
      observation that established it.

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

- [ ] **T11s · The chain walker invents sprites in script files**
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

- [~] **T11b · What is actually inside a decoded asset**
      Decoding gives bytes; the rewrite needs to know what they *mean*. The 6-byte
      header and the decoder's plane count (`ss:[0b57]`: `0x80`→1, `0xa0`→2, else 8)
      are the colour-depth story, but nothing yet says the dimensions, the plane
      layout, or where the palette comes from — the questions a CPS file answers with
      "320x200, 256 colours, palette inline".
      **Done when:** FORMATS.md states, for one decoded image asset: width, height,
      bit depth, plane order, and whether the palette travels with the file or comes
      from elsewhere — each derived from the code or from a byte-for-byte comparison,
      not from the picture looking right.
      *Partly done (FORMATS §3.7): 8 bpp, one linear plane, and the decoded bytes are
      byte-identical to what the game writes to VGA memory — logo.io's image is 144 px
      wide, drawn near x=88, with transparency. Still open: height, because a file holds
      several images; where the palette comes from; and the geometry's source, since the
      width is not a plain word in the header. `tools/io2png.py` renders assets now,
      taking the width as an argument.*
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

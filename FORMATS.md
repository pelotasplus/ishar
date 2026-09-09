# Ishar 1 — file and data formats

Byte-level specification, written to be implementable in Kotlin without an emulator.
Game mechanics live in `FINDINGS.md`.

Every format section carries a **Status** line — `specified`, `partial`, or
`unknown` — and a **Verified by** line. A decoder is only `specified` once it
reproduces bytes the emulator holds in memory, on more than one input file.

---

## 1. `start.exe` — the packed executable

**Status:** specified
**Verified by:** `tools/verify-unpack.py` — runs the shipped binary under Spice86,
stops where the decompressor finishes and again at the real entry, and compares all
88,614 bytes against `tools/unpack.py`'s output with relocations applied. Prints
IDENTICAL.

```
start.exe          43,265 bytes  sha1 51eff92347f5aa49f36baa908d5af0e4b7724be5
start-unpacked.exe 89,206 bytes  sha1 425a39733144b2edeba813a6608f741a26ef937f
                   image 0x15a26 = 88,614 bytes
```

Both live in `ishar_legend_of_the_fortress_DOSGamer.com/`; the unpacked one is derived
and gitignored, and is what `run.sh` boots. It loads at the same segment as the packed
original (`017d` in every run measured), so a runtime address means the same thing
either way.

### 1.1 MZ header (packed)

| field | value | note |
|---|---|---|
| header size | 2 paragraphs (32 bytes) | image starts at file offset `0x20` |
| relocations | 1 | the program's real table is carried in the compressed data |
| `CS:IP` | `0000:0003` | entry is the third byte of the image |
| `SS:SP` | `15FA:0080` | the packer's stack, not the program's |
| minalloc | `0x0B73` paragraphs | |
| overlay field | `0x80` | non-standard; typical of a packer |

### 1.2 Entry stub (image `+0x0003`)

Copies the whole image up by `0x0b64` paragraphs (16 bytes per iteration, `0xa97`
iterations), then far-jumps into the copy. The jump's segment word at `+0x0038` is
patched by `add [0138],ax` — reachable because DS is still the PSP at entry, so
`(load-0x10)*16 + 0x138 = load*16 + 0x38`. `push cs` at `+0x0006` leaves the load
segment on the stack for the relocation phase.

On arrival: `DS = load+0x0b63`, `ES = load-1`, `DI = 0x10` (left by the last
`rep movsw`), `SI = 0x4a`, `BP` = the first bit-stream word, `DL = 0x10`. In image
terms that is source `+0x003c` reading forward out of the copy, destination `+0x0000`
writing forward — the copy exists so the two never collide.

### 1.3 Compression — LZEXE-family bit-stream LZ

Forward decompression. A bit stream of 16-bit little-endian words, LSB first, refilled
when a counter runs out (`get_bit`, `seg000:a7e3`). Tokens:

| bits | meaning |
|---|---|
| `1` | literal: copy one byte from the source |
| `0 1` + byte | short match: 2 more offset bits, then a length (below) |
| `0 0 1` + byte | long match: 3 more offset bits into the offset's high byte, minus 1; length 2 |
| `0 0 0` + byte ≠ `0xff` | length-2 match at offset `0xff:byte` |
| `0 0 0` + `0xff` + `1` | re-base ES:DI / DS:SI; linear-preserving, a no-op with flat buffers |
| `0 0 0` + `0xff` + `0` | end of stream |

Offsets are negative 16-bit displacements (high byte starts at `0xff`), so every match
is a back-reference into the output. Short-match lengths: 3..6 from a four-step unary
run, else 7 or 8 from two more bits, else 9..16 from three bits plus 9, else a literal
length byte plus `0x11`.

### 1.4 Relocation table

**Not in the packed file.** It is compressed together with the program and lands at the
end of the decompressed image, at output offset `0x1590a` — the packer's own
`(load+0x158c):004a` — occupying the last `0x11c` bytes, which end exactly at the
image end. 138 records (`0x8a`), each producing one fixup:

- a word with bit 15 clear is a segment (unbiased; the stub adds the load segment),
  followed by an offset word;
- a word with bit 15 set is a 15-bit signed delta on the current offset.

### 1.5 Entry point and stack

The stub ends with `jmp far 0000:25e5`, whose segment word reads `0000` in the file and
`017d` in memory — the relocation loop patches it — so the unbiased entry is
**`0000:25E5`**. The stack is set to **`158D:0000`** (`add bp,158dh / mov ss,bp /
mov sp,0`), which is not the packed header's `15FA:0080`.

Emitted image keeps the full 88,614 bytes including the relocation-table tail, so the
file matches memory byte for byte and the verifier's length check stays exact.

## 2. `start.stp` — launcher settings

**Status:** specified
**Verified by:** reading the parser at `seg_13d7:0e96` (`load_settings`), which opens
the file, reads 14 bytes, and validates and consumes them byte by byte. Every mapping
below is a `cmp`/`jz` in that routine, not an inference from the string.

14 bytes, ASCII, no separators — **seven key/value pairs**, key at even offsets, value
at odd. The parser checks all seven key letters and rejects the file if any is wrong:

```
offset  0  1  2  3  4  5  6  7  8  9 10 11 12 13
        R  ?  V  v  S  s  P  p  J  j  M  m  K  k
```

The shipped file is `RBVVSAP1J0M1KQ`.

| pair | value | meaning | stored at |
|---|---|---|---|
| `R` | *(never read)* | key checked, value ignored by this parser | — |
| `V` | `C`=0 `E`=1 `V`=2 `H`=3, else 3 | video: CGA, EGA, VGA, Hercules | `cfg_video` `seg_13d7:03a6` |
| `S` | `I`=0 `A`=1 `B`=2 `N`=3 `G`=4 `C`=4 | sound device; `A` is AdLib. `C` also sets `seg_13d7:0b8e` to 8, so `C` and `G` share a value and are told apart by that byte | `cfg_sound` `seg_13d7:05fc` |
| `P` | digit − `'1'` | port | `cfg_port` `seg_13d7:066a` |
| `J` | digit − `'0'` | joystick | `cfg_joystick` `seg_13d7:0402` |
| `M` | digit − `'0'` | mouse | `cfg_mouse` `seg_13d7:048a` |
| `K` | `A`=0 `Q`=1 `Z`=2, else 0 | keyboard layout: AZERTY, QWERTY, QWERTZ | `cfg_keyboard` `seg_13d7:0574` |

After parsing, each value is range-checked and replaced from a default if out of range:
video against 4, sound against 5, port against 4, mouse against 2, joystick against 3.
Any DOS failure — or a wrong key letter — jumps to `0x0fde`, which sets
`settings_invalid` (`seg_13d7:0b90`) and leaves every setting at its default.

So the shipped file means: VGA, AdLib, port 1, no joystick, mouse on, QWERTY. The
earlier guess-table read `SA` as "sound = Adlib" and `KQ` as "keyboard = QWERTY" and was
right about those two, but it also invented a meaning for `R` that the code never reads,
and guessed `VV` as one field when `V` is the key and the second `V` is its value.

`cfg_keyboard` is the setting behind FINDINGS §2.1: the game ships QWERTY letter rows
with a French number row, and this is the byte that selected them.

## 3. `.io` / `.fic` — the asset container

**Status:** unknown

108 files, 730 B to 76 KB. All share an 11-byte signature at offset 2:

```
offset 0  u16   varies per file (size? chunk count? — unverified)
offset 2  A1 01 00 0B 09 0A 0B 07 05 06 07      identical in every file sampled
offset 13 ...   payload
```

Sampled headers:

```
iboishar.io  7e06  a1 01 00 0b 09 0a 0b 07 05 06 07 ...
presen.io    fe30  a1 01 00 0b 09 0a 0b 07 05 06 07 ...
ville.io     6e89  a1 01 00 0b 09 0a 0b 07 05 06 07 ...
mcave.io     1652  a1 01 00 0b 09 0a 0b 07 05 06 07 ...
```

A fixed table repeated in every file suggests a compression scheme with a static code
table rather than a per-file one.

Names group by content: `text*.io` and `message*.io` are per-language text
(`textin/textind/textine/textini`, `messagee/messagei`), area names (`foret`, `ville`,
`plaine`, `mcave`, `temple`) look like scenes, creature names (`dragon`, `spectre`,
`zombi`, `minotor`) look like sprite sets, `cont1..6.fic` are six identical-sized
(4860 B) files.

### 3.0 The 6-byte header

Every asset starts with three little-endian words, read to `ss:2480` before anything
else. Each is named by the code that consumes it, at `seg_0000:7801` (catalogue path)
and `seg_0000:793a` (direct path).

| bytes | name | meaning |
|---|---|---|
| 0-1 | `hdr_size` | total size, headers included. 22 is subtracted on the catalogue path (6 + 16), 6 on the direct path |
| 2-3 | `hdr_mode` | high byte `and 0feh` becomes the decoder's mode at `ss:[0b57]`: `0x80` one pass, `0xa0` two, anything else eight. Low byte is a parameter used when the mode's sign bit is set |
| 4-5 | `hdr_is_catalogue` | **the discriminator.** Zero → read the 16-byte directory next; non-zero → decode straight away |

Measured over all 106 `.io`/`.fic` files:

```
blancpc.io   2100 bytes   34 08 00 00 01 00   size 2100 = file size, mode 0x00
logo.io     14420 bytes   be 9e 00 a1 01 00   size 40638, mode 0xa0
main.io     11240 bytes   26 67 00 a1 00 00   size 26406, mode 0xa0, catalogue
```

- `hdr_is_catalogue == 0` in exactly **5** files: `main.io` and four `.fic`
  (`cont1`, `cont2`, `cont6`, `en1`) — and those four have an all-zero header, so they
  are probably not this format at all.
- `hdr_mode` is `0xa0` in **97** of 106; the rest are `0x00`, `0x02` or `0xcc`.
- `hdr_size >= file size` in 93 of 106, consistent with a decompressed size.
  `blancpc.io` is the one asset seen to load uncompressed, and there the two are equal —
  which is also why it is read whole in a single call instead of in chunks.

This replaces the earlier guess of "an 11-byte signature at offset 2". There is no
signature: `a1 01 00` is simply the high byte of `hdr_mode` followed by
`hdr_is_catalogue`, and it looks constant because almost every asset shares one mode.

**Verified by:** the annotated disassembly of both header readers, and the field values
tabulated across every asset file.

### 3.1 How the game reads one

Traced with `tools/gdbtrace.py` from a paused start:

```
open  MAIN.IO
read  6 bytes    -> 0d88:2480     a 6-byte header, into a scratch buffer
read  16 bytes   -> 0d88:2486     16 more bytes of header
read  8000 bytes -> e000:0000     payload, in 8000-byte chunks
read  8000 bytes -> e000:0000     ... same buffer, so it is streamed and consumed
close
```

`blancpc.io` (2500 bytes) is instead read whole in one call to `1123:0000`, so small
files skip the chunking.

This contradicts the guessed layout above: the header the game reads is **6 bytes**,
followed by a 16-byte block, not an 11-byte signature at offset 2. The decoder must be
read from the code that consumes those buffers.

### 3.2 The loader and the decoder (partial)

`load_container` at `seg_0000:76bc` opens the file and reads the two headers:

```
6 bytes  -> ss:2480     header
16 bytes -> ss:2486     a table of counts, not compressed data
```

Those 16 bytes are a **directory**: the loader carves the destination memory into
sub-arrays from them — `ss:[2486]` sizes one region, `ss:[2488]` counts 6-byte
elements, `ss:[248e]` a region rounded up to paragraphs, `ss:[2492]` counts
`0x26`-byte elements. Element sizes are read off the code, not guessed.

**There are two decoders, chosen by mode.** At `seg_0000:7a2a` the code masks
`ss:[0b57]` with `0xf0` and compares against `0xa0`: a match calls `seg_0000:7b85`,
anything else falls into the loop at `seg_0000:7a79`. Since 97 of 106 files are mode
`0xa0`, **the common path is `0x7b85`, not the RLE loop below.**

#### Mode 0xa0 — bit-packed LZ77 (`seg_0000:7b85`)

**Status: specified.** `tools/io.py` implements it and reproduces the emulator's own
decode byte for byte.

The payload is an **8-byte table of offset bit-widths** followed by a bit stream. The
game copies that table into its own code at `cs:[7cb7]` — self-modifying — and indexes
it with a 3-bit code. Bits are read most-significant first (`0x7ceb`; `0x7ce9` is the
same reader with a count of 3). `0x7cbf` is not a bit reader at all: it is the
end-of-output check.

Each round is an optional literal run followed by a match:

```
1 bit          1 -> a literal run follows; 0 -> go straight to the match
  run length   2-bit groups, summed, continuing while a group reads 3, then + 1
  literals     that many bytes, 8 bits each
3-bit code c   table[c] is the offset's bit width; c & 3 carries the length
  c & 3 != 0   length = (c & 3) + 1, then read table[c] bits as the offset
  c & 3 == 0   read the offset first, then 3-bit groups summed while they read 7,
               length = sum + 5
copy           from out[si - offset - 1], forward, one byte at a time
```

`logo.io`'s table is `11 9 10 11 7 5 6 7`, so an offset costs 5 to 11 bits depending on
the code — short codes for near matches.

Decoding runs off the end of the stream by a few bits on the last token; the original is
still reading its 8000-byte input buffer there, so those bits are whatever the previous
read left. `tools/io.py` supplies zeros, which is why `logo.io`'s **final byte** differs
from the emulator's and the other 40,631 match exactly.

**Verified by:** `main.io` — all 26,384 bytes identical to `.ish/main-decoded.bin`;
`logo.io` — 40,631 of 40,632 identical to `.ish/logo-decoded.bin`, the exception being
that last byte. Both captured from the running game with `tools/t11-capture.py`.
97 of the 106 asset files decode with it; the other nine are modes `0x00`, `0x02` and
`0xcc`, which take the RLE path below or are not this format at all.

The **byte-oriented RLE decoder** below serves the other modes:

| address | name | what it does |
|---|---|---|
| `seg_0000:7a79` | `rle_decode_loop` | one pass per plane; `ss:[0b18]` counts planes down |
| `seg_0000:7ade` | `get_byte` | next input byte, refilling when `BX` reaches `ss:[0b3a]` |
| `seg_0000:7aee` | `read_next_chunk` | refill: 0x1f40 (8000) bytes into the buffer at `ss:[0b5a]` |
| `seg_0000:7b06` | `put_byte` | write one byte to `ds:[si]`, bounds-checked |

Its pass count comes from `ss:[0b57]`: `0x80` → 1, anything but `0xa0` → 8. A control
byte below `0x80` copies `c` literal bytes; `c >= 0x80` repeats the next byte `c & 0x7f`
times. Each pass writes every `stride`-th output byte, pass *p* starting at offset *p*,
so the passes interleave — `put_byte` advances `si` by the stride and the pass ends on a
bounds check rather than a counter.

`tools/io.py` implements exactly this, and fails loudly on the `0xa0` files it cannot
yet decode: 65 of 106 produce output, and even those leave most of the payload
unconsumed, which is the signature of decoding the wrong scheme.

### Ground truth

`.ish/logo-decoded.bin` — 40,632 bytes, the emulator's own decode of `logo.io`, captured
by `tools/t11-capture.py` (break where the header is consumed, read the output pointer
from `ss:[0bc8]`, break again at the close, dump `hdr_size - 6` bytes). Regenerate with
`tools/ish start --gdb --pause && tools/t11-capture.py`. Any decoder claiming to work
must reproduce this byte for byte; it begins
`40 00 16 00 00 17 00 00 00 00 16 00 00 00 68 02`.

### 3.5 The catalogue's contents (T11e, partial)

`main.io` decodes to 26,384 bytes that are **a tagged stream, not a record array**.
Filenames live in it — 241 of them — in entries shaped:

```
45 <id> 00 <name>\0        introduces an asset: one-byte id, then its filename
0a <u16> 00 00             prefixes each member of a language group
```

`logo.IO` is `45 40 00 "logo.IO"` → **id 0x40**. 225 entries match that exact shape.

**The language variants are in the data, four to a group, always in the same order —
`e`, `d`, `i`, then no suffix:**

```
0a 39 00 00  45 63 00  messagee.IO
0a 34 00 00  45 64 00  messaged.IO
0a 21 00 00  45 65 00  messagei.IO
0a 0e 00 00  45 0e 00  message.IO
```

and likewise `sose/sosd/sosi/sos`, `textine/textind/textini/textin`. Each variant has
its **own id**, so the selection is not a filename transformation — the game asks for a
different asset number, and the `0a` word before each is presumably what the language
choice tests.

**Verified by:** the decoded bytes of `main.io`, which are themselves verified byte for
byte against the emulator (§3.2). **Not yet verified:** that a live load of `logo.IO`
requests id `0x40` — the run that would have confirmed it died on the FPU fault in
FINDINGS §5.2 — and what consumes the `0a` prefix.

### 3.4 Assets are addressed by id, not by name

Only **three** filenames exist anywhere in the 88 KB image: `blancpc.io`, `main.io` and
`MAIN.IO`. Every other file — `logo.IO` included, which we have watched load — is
reached without its name appearing in the code.

`load_asset_by_id` (`seg_0000:78f9`) takes an id in `ss:[0b04]`. Zero means `main.io`
itself. Anything else goes to `find_asset_record` (`seg_0000:8106`), which walks an
index of far pointers — base `ss:[0bc2]`, count `ss:[0bce]`, four bytes per entry — and
compares the wanted id against the first word of each record it points at. It returns
the record's far address, or `0xffff` for an id that is not there.

So **`main.io` is the catalogue**: loaded first, it carries the index and the records
that every later load goes through. That explains its extra 16-byte directory, which
sizes exactly this kind of thing — an array of 6-byte elements and an array of
`0x26`-byte records among them.

For the rewrite this is the shape that matters: the game does not open files by name,
it asks for asset *N*. Any port needs the catalogue decoded before a single sprite can
be found, which makes `main.io` the first thing `tools/io.py` has to read.

**Verified by:** the annotated disassembly of both routines, plus the string search that
found only three filenames in the image.

### 3.3 Who reads what (T10b)

Reading one word past the interrupt frame names the routine that wanted the file, not
the DOS wrapper. Observed:

| file | header reads | chunk refills | driver |
|---|---|---|---|
| `main.io` | 6 bytes, then 16 (`load_container` `0x76cf`, `0x76d8`) | `0x7bb1` then `0x7d3e` | closed by `0x7839` |
| `logo.IO` | 6 bytes only (`load_logo_io` `0x7924`) | `0x7bb1` then `0x7d3e` | opened by `0x791a` |
| `blancpc.io` | — | none; 2500 bytes in one call | `load_small_file` `0x06d3` |

Two things fall out. **`main.io` has the 16-byte directory and `logo.IO` does not**, so
that block is specific to the data container, not part of every file. And **both files
are consumed by two different decoders in sequence** — the first chunk refills through
`refill_chunk_a`, the second through `refill_chunk_b`.

This also corrects §3.2: the refill annotated there (`0x7aee`) is a *third* copy of the
same helper that nothing has been observed to reach. It is renamed
`refill_chunk_c_unobserved`. The lesson is in CLAUDE.md — a plausible routine found by
reading is not the routine in use until the machine says so.

**Verified by:** live INT 21h trace with the outer caller read from `SS:SP+6`
(`SS:SP+8` for opens, which push AX first), two runs, `main.io` and `logo.IO`.

**How this gets specified:** not by staring at the bytes. Break on the game's file
read, note the destination buffer, let the decompressor run, and diff input against
output — the routine in between is the decoder. Port it, then check it reproduces the
emulator's buffer byte for byte on several files.

---

### 3.7 What is inside a decoded asset (T11b, partial)

**Established, byte for byte.** A decoded asset holds **8-bit palette indices, one byte
per pixel, laid out linearly** — the same values the game writes to VGA memory. Proven
by capturing the emulator's framebuffer while the Silmarils logo was on screen and
finding those exact bytes inside decoded `logo.io`:

| what | value | how |
|---|---|---|
| bit depth | 8 bpp | decoded bytes equal VRAM bytes exactly |
| planes | one, linear | no interleaving needed to make them line up |
| row stride | 144 bytes for `logo.io` | fitted across 15 rows, all agreeing on 144 |
| image width | 144 px | the same 144, since 1 byte = 1 pixel |
| draw position | around x=88 | where the agreement starts on the widest row |
| transparency | yes | agreement ends mid-row where the screen shows background `0x05`, so those pixels are not written |

`captures/asset-logo-verified.png` is the verified region rendered at 144 px wide with
the DAC palette captured at the same moment — it is a recognisable piece of the logo.

#### The sprite header — 8 bytes, and it carries the geometry

```
word 0   purpose unknown (1812 for the logo)
word 1   width  - 1     <- what the blitter reads as [si+2]
word 2   height - 1
word 3   flags? (0 for the logo, 128 for the next sprite in the file)
```

then `width x height` bytes of 8-bit indices. **Colour index 0 is transparent.**

Verified on `logo.io`'s sprite at offset 1856: the header says `144 x 118`, and comparing
those 16,992 pixels against the framebuffer while the logo was on screen gives
**12,875 identical and 4,117 differing — every one of them decoded `0x00` against the
screen's background `0x05`**. Identical plus transparent accounts for 100% of the sprite,
which is what makes index 0's meaning a measurement rather than an impression.

It was drawn at (84, 11). That position is **not** in the header — the blitter takes it
from `ss:[0c2c]`/`ss:[0c2e]`, set by whoever asks for the draw.

`tools/io2png.py logo.io out.png --at 1856` now reads the geometry from the header
instead of being told a width. `captures/asset-logo-sprite.png` is the result.

**Where it is not.** Four places were searched and ruled out, so the next attempt does
not repeat them:

- **Not an offset table at the head of the file.** `logo.io`'s first 1,856 bytes contain
  monotonic word runs, but they are evenly-spaced ramps (steps of `0x1001`, `0x2222`) —
  shading or fade tables, not offsets. The values `1856`, `1864` and `18856` appear
  nowhere in that head.
- **Not in the catalogue.** `main.io` does not contain the sprite's offset either; the
  entry for `logo.IO` is just `45 40 00 "logo.IO"` with unrelated bytes around it.
- **Not derivable by chaining.** Walking headers works for `logo.io` — the correct start
  ranks first of only two candidates that yield a two-sprite chain — but `presen.io` and
  `dragon.io` produce no chain at all, so sprites are not laid end to end in general.
- **Not a palette either** (§3.9): the only 768-byte run of values ≤ 63 in `logo.io` is
  inside the sprite's own pixels.

**How the game does it: a far pointer, passed in.** Breaking on `draw_sprite`
(`seg_0e97:038b`, 445 calls in a boot) shows `DS:SI` arriving already pointing at a
sprite's 8-byte header, normalised so `SI` is 8 to 12 — and pointing into *several
different* loaded buffers, not just the most recent one. Headers seen live: 48x48,
32x20, 16x1, all matching §3.7's layout. The callers are `seg_0e97:0534` and `:055e`.

So a sprite is found by a far pointer the caller already holds; the question is where
that table of pointers is built. **Still open**, and the next step is one level further
up: decode the callers and see where the pointer is loaded from.

**Still open:** how a sprite is located inside a file. Walking from 1856 finds the logo
and then a 16x13 sprite at 18856, after which the headers degenerate, so there is a
directory rather than a plain sequence. The file's first word is `64` — `logo.IO`'s own
asset id from the catalogue (§3.5) — so the head of each file is likely keyed the same way.

**Not established.** Height per file, because a file holds **more than one image**: 40,632 bytes
is 282 rows of 144, far more than a 200-line screen, and rendering the whole file at 144
shows the logo followed by other content. And the width is **not** a plain word in the
header — `144`, `88` and `110` appear nowhere in the first 300 bytes. Where the palette
comes from is also open: we used the DAC as the emulator had it, which does not show
whether the file supplies it.

`tools/io2png.py` renders any asset to PNG, taking the width as an argument because of
exactly that gap; a wrong width shears the image diagonally, which makes it easy to
judge by eye but is not proof.

**Verified by:** `.ish/logo-vram.bin` (the emulator's 64,000-byte framebuffer) against
the decode of `logo.io`, captured by `tools/t11b-capture.py`.

### 3.8 The drawing system (T11i, partial)

Mode 13h, set by `int 10h` at `seg_0e97:0ccd`. Immediately after, the game stores a
**far pointer to the drawing target** — `draw_target_seg:draw_target_off`, initially
`a000:0000` — and a **row stride** `row_stride` = `0x140` (320). The pointer is swapped
at `seg_0000:4370`, so drawing can go to an off-screen buffer and be copied later.

Two blitters use them:

- `blit_rect` (`seg_0e97:0148`) copies a rectangle between two buffers that share the
  stride, taking its bounds from the clip variables `clip_left`, `clip_top`,
  `clip_right`, `clip_bottom` — set to the full screen `(0,0)-(319,199)` by
  `set_full_screen_clip`. This is page work, not sprite drawing.
- A **sprite blitter** around `seg_0e97:0330-03d0` takes its geometry from the sprite
  itself: `[si+2]` is a dimension and `add si, 8` steps over an **8-byte header** before
  the pixels. It also consults a descriptor at `ES:DI`, testing bit 0 of byte `+0x22`
  to choose between two paths — almost certainly a horizontal flip. `0x22` sits inside
  the `0x26`-byte records that `main.io`'s directory counts (§3.0), which is the first
  concrete link between the catalogue's records and drawing. Draw position comes from
  `ss:[0c2c]` and `ss:[0c2e]`.

**So an asset's width is not carried next to its pixels.** Searching the decode of
`logo.io` for a word of 140-148 anywhere in the 400 bytes before the verified image
found nothing, and the eight bytes immediately before it are not a plausible header.
The likely source is the `0x26`-byte descriptor record, which is where T11i continues.

This also explains the distortion at the top of `captures/asset-logo-verified.png`: the
296-byte offset it renders from was **fitted from a pixel match, not derived**, so the
first rows include bytes that are not part of that image.

**Verified by:** the annotated disassembly of both blitters and the mode switch; the
byte-level search that ruled out a width field near the pixels.

### 3.9 The palette travels with the asset (T11j)

**Corrects an earlier entry in this file**, which said `logo.io` carried no palette. It
does. The first search looked for the DAC's **6-bit** values as captured; the file stores
**8-bit** RGB, so nothing matched and the wrong conclusion was recorded.

How it reaches the screen:

1. `seg_0000:74b5` copies from the decoded asset — `DS:SI` was `2365:0031`, and `2365`
   is `logo.io`'s own decode buffer — into a DGROUP staging buffer at `ss:0e46`.
2. `seg_0e97:0d5f` writes that buffer out to the VGA DAC data port `0x3c9`.

The stored form is **256 entries of 3 bytes, 8 bits per channel**. The DAC gets each byte
shifted right by two: `dac = byte >> 2`. Verified for **768 of 768** bytes against the
palette captured while the logo was on screen — `0xda -> 0x36`, `0xff -> 0x3f`,
`0xb5 -> 0x2d`, with no exceptions.

That also means an asset's palette is *already* in the form a PNG wants, and
`tools/io2png.py --palette-at OFFSET` now uses it directly.

**Where it sits is per-file.** In `logo.io` the palette is at offset 992, but only 2 of
93 decodable files have anything palette-shaped there — so the offset is carried
somewhere, exactly like the sprite offsets of §3.8. The two questions have one answer,
and finding it closes both.

So, unlike Eye of the Beholder's separate `.PAL` files, Ishar ships each asset with its
own palette inside the same compressed file.

**Verified by:** an IO breakpoint on port `0x3c9` and a memory-write breakpoint on the
staging buffer, both naming their writers; then the byte-for-byte shift check.

#### The palette is 16 sub-palettes of 16 (T11m)

Dumped in-game, the DAC has 227 non-zero entries laid out as **16 groups of 16**, and
every group from 1 upward begins with white then black:

```
  0: 000 000 420 642 964 b96 b00 040 260 692 fb0 046 269 499 9b9 ddb
 16: fff 000 520 630 741 962 a73 c95 db7 230 340 460 670 880 990 ba0
 32: fff 000 643 754 865 976 a98 ca9 fc0 353 464 574 785 995 dcb 778
 ...
240: fff 000 000 000 ...                       (unused tail)
```

Group 0 is the exception -- it starts black, because index 0 is the transparent
colour. That white/black boundary every 48 bytes is a strong enough signature to
find a palette in a file without being told where it is, which is what
`tools/ioscan.py` now does.

**The whole 768-byte block is stored in the asset, 8-bit RGB.** Searching every
decoded asset for the DAC as captured in-game gives exact hits:
`fond.io @ 12108` and `geren.io @ 6684`, both **768/768 bytes**.

**Only scene files carry a palette.** Nine of about 110 assets contain one: `fond.io`,
`fcave.io`, `fcave2.io`, `frise.io`, `ftemple.io`, `fville.io`, `itaverne.io`, `geren.io`
and `gerdep.io`. The `f` prefix is *fond*, French for background. Every other asset --
monsters, objects, characters -- carries none and is drawn against whatever palette the
current scene loaded. Extracting one of those in isolation therefore cannot get its
colours right without knowing the scene (T11m2).

#### `geren.io` is the palette bank

`geren.io` holds **12 unique 768-byte palettes** and `gerdep.io` another 5, and four of
the seven palettes found inside scene files are byte-identical entries in them:

| scene file | its palette | is |
|---|---|---|
| `fond.io` | 12108 | `geren#0` |
| `fcave.io` | 1310 | `geren#2` |
| `fcave2.io` | 5712 | `geren#2` |
| `ftemple.io` | 16244 | `geren#11` |
| `frise.io` | 34700 | `gerdep#0` |
| `fville.io` | 1304, 1352 | not in the bank |
| `itaverne.io` | 5946 | not in the bank |

So scene files embed a copy of the bank entry they use, and the ~100 assets that carry
no palette borrow one at runtime. `tools/ioscan.py` defaults those to `bank#0` -- a
placeholder, not the answer: which entry a given sprite is drawn against is T11m2.

`geren.io`'s offsets are `6684, 7408, 7456, 9180, 9904, 9952, 10724, 11448, 11496,
12172, 12220, 12268` -- note the recurring `+724` and `+48` steps, which suggests the
bank has a record structure of its own that has not been read yet.

**A scene file can carry more than one palette.** `fond.io` has valid blocks at 556 and 12108,
`geren.io` at 6540-ish, 6684 and 12268, `logo.io` at 992 and an identical copy at
20172. The one in use for a given scene is *not* determined yet -- for `fond.io` the
live one sat just past the end of the sprite chain, but that heuristic picks the
wrong block for `geren.io`. See T11m2.

Two encodings are in play and confusing them cost a session: the game writes the DAC
with a 6-bit `>> 2`, but Spice86 reports the palette scaled back to 8 bits, so the
values it returns compare **directly** against the file's bytes -- not shifted.

**Verified by:** `.ish/game-palette.json` (in-game DAC) matched byte for byte against
`fond.io` at 12108 and `geren.io` at 6684 by exhaustive search over all decoded assets.

### 3.10 Sprites are 4 bits per pixel, and they chain (T11k, T11l)

**This is the piece that was missing, and it invalidates every "the decoder is broken"
theory tried before it.** The blitter's row arithmetic at `seg_0e97:03f1` is

```
mov bx,[si+2]     ; width - 1
inc bx            ; width
mul bx            ; y * width
shr ax,1          ; ... / 2      <- two pixels per byte
```

and the same `shr ax,1` appears on the x offset at `:0398`, `:041d` and `:045f`.
So a sprite row is `ceil(width/2)` bytes, **high nibble first**, and an index is 0..15.

**Sprites are stored back to back.** A record is the 8-byte header plus
`ceil(width/2) * height` bytes, and the next header follows immediately:

```
record size = 8 + ceil(width/2) * height
```

Measured on 30 sprites captured live at the blitter: the gap between consecutive
sprites in a buffer equals that expression in every case (112x24 -> 1352, 96x169 ->
8120, 80x168 -> 6728, 112x51 -> 2864). Chaining was tried before and rejected because
8bpp made the arithmetic wrong at the first step, which looked like "there is no chain".

That answers T11k without a directory: **walk the chain.** `tools/ioscan.py` picks the
start offset whose chain explains the most of the file and walks it — 811 sprites out
of 75 files, with the chain accounting for 80-95% of the bytes in the good cases.

**Word 3 is not the depth (T11l).** Every sprite measured is 4bpp regardless of it —
values 0, 16, 32, 128, 160, 162-165, 47872 all came out 4bpp by the spacing oracle. It
does carry something: `162, 163, 164, 165` sit on sprites of 96x169, 80x168, 64x166,
48x162 — a shrinking sequence, so it reads as a **distance/perspective slot in the 3D
view** rather than a pixel format.

**Depth is per-path, not per-sprite.** `logo.io`'s sprite at 1856 is verified
byte-for-byte as **8bpp** against the framebuffer (3.7), and its neighbour sits exactly
`8 + w*h` away, so the title screen genuinely uses a separate 8bpp blitter. Finding that
routine is what is still open.

**Verified by:** `tools/t11m-sprites.py` reads 30 sprites out of emulator memory at the
blitter breakpoint; `captures/blit-sheet.png` renders them 8bpp (unreadable) and
`captures/blit4-sheet.png` 4bpp (the ISHAR title lettering, "LEGEND OF THE FORTRESS"
and the parchment art, all clean). `captures/assets-contact-sheet.png` is the static
extraction over the whole game.

#### Word 0 is `flags | group`, plus a colour count (T11q)

```
word 0  low byte   16 for 742 of ~800 sprites -- the colour count (4bpp)
                   18 and 20 also occur; nothing above 32 is a sprite
word 0  high byte  bits 0..3  palette group (0..15, see 3.9)
                   bits 4..7  flags: 0x00 on 743 sprites, 0x20 on 50,
                              0x10 on 9. Meaning not yet known.
```

The flag nibble is only ever `0x00`, `0x10` or `0x20` across the whole game; `0x30`,
`0x40`, `0x60` and `0xf0` turn up a handful of times each and are the chain having lost
sync. That makes word 0 a **validity test**, and applying it inside the chain walk stops
a bad chain scoring well rather than filtering its output afterwards: 811 records became
786, and rendering the 25 rejects shows scanlines and static, no art
(`captures/t11q-dropped.png`).

Reading the group as the *whole* high byte -- as this file previously did -- silently
mis-coloured the 50 sprites carrying `0x20`, because their apparent group of 32..47 fell
outside the 16 the DAC has.

**Verified by:** the flag/group split is a census over every chain record in all 106
decodable assets; the rejects were rendered and inspected.

**How a 4bpp index becomes a colour (T11m).** The DAC is 16 sub-palettes of 16 (3.9), so

```
vga_index = group * 16 + nibble        group = header word 0 >> 8
```

Header word 0 was the last unexplained field, and its high byte is the group: the
values read live were `0x0012, 0x0017, 0x0310, 0x070f, 0x0b00, 0x0c14, 0x0e10` --
a group index in the high byte and a small low byte. Rendering everything as group 0
is what left the shapes right and the colours wrong.

**Independent confirmation of the palette work:** reading the framebuffer at `0xA0000`
over GDB and rendering it with the palette recovered from `fond.io` reproduces the game
screen exactly, colours included (`captures/t11m2-vram.png` against
`captures/t11m2-state.png`). That validates 3.9 end to end -- the file's 768 bytes really
are the DAC the game is running.

**Status:** the mapping is established from the DAC's structure and word 0's shape,
and it is *not yet* confirmed pixel-by-pixel against the framebuffer -- the one
attempt matched 32/40 opaque pixels of a 16x4 sprite, which is not enough to call it.
See T11m.


## 4. Video

**Status:** unknown

Spice86 reports the display as 640x400x8 (`BufferSize` 256000). Whether that is a
tweaked VGA mode or Spice86's presentation of a 320x200 mode has not been established,
and it matters for how textures are laid out in the rewrite.

**Verified by:** `read_video_state`.

**Open:** actual mode set by the game, palette handling, framebuffer layout, sprite
format, and the scaling rule for the first-person view.

---

## 5. Save games

**Status:** unknown — no save has been produced yet.

## 6. The script VM's instruction encoding (T26, T28)

A script is a byte stream. `SI` is the program counter, `DX` the accumulator, `BX` an
evaluation stack pointer reset to `0x277c` at every statement, `ES:BP` the local frame
and `ss:[0bf6]` a second base for globals. Operands follow their opcode inline.

**Four dispatch tables**, and they do **not** share an indexing convention -- getting this
wrong makes the opcode numbers meaningless:

- `vm_statement_table` is **word-scaled** (`call cs:[bx+24h]` with `bx = opcode*2`), so its
  opcodes run 0..230 and take every value.
- The three expression tables are indexed by an **unscaled** byte (`jmp cs:[di+1f2h]`), so
  their opcodes are even and a table of N words holds N/2 opcodes.


| table | image offset | entries | what it dispatches |
|---|---|---|---|
| `vm_statement_table` | `0x0024` | 231 entries, opcodes 0..230 | statements, control flow, engine primitives -- **word-scaled** |
| `vm_opcode_table` | `0x01f2` | ~120 | **load**: value -> accumulator |
| `vm_store_table` | `0x029c` | ~56 | **store**: accumulator -> variable |
| add-assign table | `0x02d8` | ~84 | **`+=`**: accumulator into variable |

The lower three are the same addressing-mode matrix three times over -- the same access
repeated once per operand width (byte or word immediate) and once per mode (direct,
indexed via `vm_index_byte`/`vm_index_word`, far via `vm_index_far`, frame-relative or
global). That is why 120 handlers describe so few actual operations.

### Control flow

| opcode | handler | encoding |
|---|---|---|
| `0x24` | `vm_op_jump_rel8` | `lodsb`, sign-extend, branch |
| `0x28` | `vm_op_jump_rel16` | `lodsw`, branch |
| `0x1a` | `vm_op_loop` | saves PC to `ss:[0c54]`, runs the body, restores it while the result is non-zero |
| `0x18` | `vm_op_wait_tick` | reads the BIOS tick at `40:6c` -- script-level timing |

Both jumps land in `vm_branch_take` (`seg_0000:274a`), which applies the displacement
with `add ax, si`. **Branches are PC-relative**, so a script is position-independent.

`vm_branch_take` also carries task bookkeeping -- a stack at `ss:[0c56]` and a frame slot
at `es:[bp-0ch]` -- which means scripts can be **suspended and resumed**, i.e. the VM is
cooperatively multitasked, not a straight-line interpreter.

### Calling the engine

There is no single "call native" opcode. Instead **each engine primitive is its own
opcode** in `vm_statement_table`, and its handler reads its arguments by calling the
expression evaluator once per argument, storing each result into a fixed engine variable:

```
vm_prim_5args (seg_0000:296b)
    call vm_dispatch ; mov ss:[0ba8], dx     ; arg 1 (word)
    call vm_dispatch ; mov ss:[0ba0], dx     ; arg 2 (word)
    call vm_dispatch ; mov ss:[0ba2], dl     ; arg 3 (byte)
    call vm_dispatch ; mov ss:[0ba4], dl     ; arg 4 (byte)
    call vm_dispatch ; mov ss:[0ba6], dx     ; arg 5 (word)
```

So a primitive's **arity and argument widths are readable straight off its handler**, and
the 195 distinct statement targets are an upper bound on the engine's script-visible API
-- which is the list a rewrite has to reimplement.

**The statement interpreter** is `vm_run` at `seg_0000:26eb`:

```
sub ah,ah / lodsb / add ax,ax / mov bx,ax / call cs:[bx+24h] / jmp back
```

Handlers are **called**, not jumped to, which is why they end in `ret` and why a primitive
can return to the interpreter. Opcodes 0..4 point at `26f9`..`26fd`, five consecutive `ret`
bytes -- no-ops.

**Status:** encoding established; individual primitives not yet identified.
**Verified by:** all four tables read from the static image and cross-checked against live
memory; handlers classified mechanically by `tools/vmops.py`, and the control-flow ones
read individually in `ishar-listing.txt`.

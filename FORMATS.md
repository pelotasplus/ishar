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

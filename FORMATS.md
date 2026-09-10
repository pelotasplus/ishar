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
| `S` | `I`=0 `A`=1 `B`=2 `N`=3 `G`=4 `C`=4 | sound device. The setup screen names them in this order: **PC Speaker, Ad Lib, Sound Blaster, Sound OFF, Sound Galaxy** (FINDINGS 4.11), so `I` is the PC speaker and `N` is off. `C` also sets `seg_13d7:0b8e` to 8, so `C` and `G` share a value and are told apart by that byte; the UI offers only one Sound Galaxy entry, so what `C` selects is still open | `cfg_sound` `seg_13d7:05fc` |
| `P` | digit − `'1'` | port | `cfg_port` `seg_13d7:066a` |
| `J` | digit − `'0'` | joystick | `cfg_joystick` `seg_13d7:0402` |
| `M` | digit − `'0'` | mouse | `cfg_mouse` `seg_13d7:048a` |
| `K` | `A`=0 `Q`=1 `Z`=2, else 0 | keyboard layout: AZERTY, QWERTY, **QWERTZU** -- the setup screen's own spelling, and it suggests AZERTY | `cfg_keyboard` `seg_13d7:0574` |

The setup screen displays five of the seven: VIDEO, JOYSTICK, MOUSE, KEYBOARD, SOUND.
`R` and the port never appear, and VIDEO is shown but not selectable. Its enumerations
match this table exactly, checked independently of the parser (FINDINGS 4.11).

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


### 3.6 Every `.io` and `.fic` file, classified

**No, they are not the same format**, and until now that was scattered across five
sections. This is the whole set -- 106 files -- classified by what is actually inside,
generated by the same code that extracts them (`.ish/file-classification.json`).

**Two layers matter and they are independent:**

1. **The container header** (3.0). `0xa100` on 88 files, `0xa101` on 6, `0xa102` on 3.
   All 98 `.io` files decode. **No `.fic` file is a container** -- all 8 fail, because
   their first six bytes are data being read as a header (3.11).
2. **The contents**, which the container says nothing about.

| contents | count | files |
|---|---|---|
| sprites | 63 | `arbre.io`, `azal.io`, `barbare.io`, `bormin.io`, `buste.io`, `colcave.io`, `darkm.io`, `darkwiz.io`, `dealer.io`, `dragon.io`, ... |
| palettes | 4 | `fcave.io`, `fcave2.io`, `gerdep.io`, `geren.io` |
| text | 18 | `blancpc.io`, `map.io`, `message.io`, `messaged.io`, `messagee.io`, `messagei.io`, `preson.io`, `saub.io`, `scave.io`, `scomb.io`, ... |
| data | 13 | `affobj.io`, `auteur.io`, `dead.io`, `dplt.io`, `encont.io`, `gaz.io`, `iboishar.io`, `monstre.io`, `param.io`, `samb.io`, ... |
| not a container | 8 | `cont1.fic`, `cont2.fic`, `cont3.fic`, `cont4.fic`, `cont5.fic`, `cont6.fic`, `en1.fic`, `tab1.fic` |

**Sprite banks are not uniform either.** A file's sprites can mix pixel formats: most use
only mode `0x10`, but `fontaine.io` carries `0x00`, `0x10` and `0x14` together, and
`itaverne.io` mixes `0x10`, `0x12` and `0x14`. So the format is per *sprite*, from word 0's
low byte (3.10) -- never per file.

| sprite mode | meaning |
|---|---|
| `0x00` | 4bpp, 6-byte header, palette base 0 |
| `0x10` | 4bpp, 8-byte header, base from word 3 -- the common case |
| `0x12` | 4bpp, 8-byte header, base from word 3 |
| `0x14` | 8bpp, index 0 transparent |
| `0x16` | 8bpp, opaque |

**Caveat on "text" and "data".** Those two buckets are a heuristic -- a file with no sprite
chain and no palette, split on whether it holds long printable runs. `message*.io`,
`textin*.io` and `sos*.io` are almost certainly language text, and `map.io` is a picture
(7.1 notes it autocorrelates at 160 = 320px at 4bpp). But `preson.io`, `saub.io`,
`scave.io`, `scomb.io`, `samb.io`, `param.io` and `souris.io` are simply **not identified**,
and the bucket name should not be read as a finding.

**Verified by:** regenerated from the files themselves; the full per-file table with byte
counts, header modes, sprite modes and counts is `.ish/file-classification.json`.

### 3.15 Every decoded asset opens with a 16-byte header

| offset | size | value | meaning |
|---|---|---|---|
| 0 | 2 | word | **asset id** |
| 2 | 6 | `16 00 00 17 00 00` | constant across **89 of 97** decoded assets — a format signature |
| 8 | 8 | varies per asset | **not identified** |

**Why "id" and not just "a number".** The value appears in two independent places and they
agree. Neither on its own would justify the name.

The id is **not present in the file on disk** -- it appears only after decompression. The
first bytes of `zombi.io` are `0e 2c 00 a1 01 00 0b 09 0a 0b ...`, which is the 6-byte
container header followed by the LZ77 offset-width table. Decompressed, the payload opens:

```
4b 00 | 16 00 00 17 00 00 | 00 00 16 00 00 00 be 02
^^^^^
word 0 = 0x004b = 75
```

And `main.io`'s script, at offset 10401, loads the file with:

```
45 | 4b 00 | 7a 6f 6d 62 69 2e 49 4f 00        ("zombi.IO\0")
^^   ^^^^^
|    id operand = 0x004b = 75
opcode 0x45 = vm_op_load_asset (section 7)
```

So the file **declares** 75 and the script **asks for** 75 by name. Across the game
**85 of 94 assets match** this way. The 9 that differ are all language variants:
`messaged/e/i` all carry `0x0e`, `sosd/e/i` carry `0x56`, `textind/e` carry `0x2f` -- so the
header id names the *content* while the script asks for a language-specific id.

For a reader this matters twice: the id is only readable after decompressing, and it is the
key the game uses to find an already-loaded asset (3.4), not merely a label.

**Verified by:** word 0 compared against the id operand of every `vm_op_load_asset`
instruction in `main.io` (section 7), across all 94 assets the script loads.



#### How much of the assets is actually understood: 42%

Summing everything this document can name -- the 16-byte asset header (3.15), sprite records
(3.10), palette records (3.9) and strings (10.3) -- across the 98 decodable `.io` files:

**673,966 of 1,583,646 bytes, 42%.**

It is very uneven. `presti.io` is 98% accounted for and `buste.io` 95%, because they are
almost entirely sprites. At the other end, eight files are at **0% beyond their header** --
`param.io`, `map.io`, `monstre.io`, `gaz.io`, `encont.io`, `dplt.io`, `blancpc.io`,
`iboishar.io` -- and the language files sit at 8-12% (10.5).

The remainder is mostly script: `main.io` is bytecode (section 7), `affobj.io` is bytecode
(section 8), and the unexplained regions inside sprite banks (9.5) and language files are
the same kind of thing. **Reading the game's art and text is solved; reading its behaviour
is not.**

### 3.7 What is inside a decoded asset (T11b)

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

#### Which palette an asset borrows (T11m2)

`main.io`'s script loads assets in order (section 7), and a palette-carrying scene is
followed by the assets drawn against it. Reading that order out of the disassembly gives
the pairing directly: **52 assets follow exactly one scene, 27 follow more than one** and
are resolved by majority. `tools/ioscan.py` reads it from `.ish/asset-scene.json` and uses
the scene's palette instead of the bank -- **79 of 88 borrowers now get a real pairing**,
9 carry their own, and 10 still fall back.

For most of the ambiguous ones the choice does not matter: measured over only the palette
indices each asset actually uses, the candidate palettes differ by less than 20 per
channel. **Nine are genuinely contested** and are the ones worth checking by eye:
`mcave` (170), `rplaine` (126), `ville` (114), `village` (98), `stage` and `intmais` (75),
`lacustre` (44), `rampart` (30), `inville` (29) -- `captures/palette-choice.png` shows each
under both candidates.

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

**How a 4bpp index becomes a colour (T11m, corrected by T11r).** The DAC is 16
sub-palettes of 16 (3.9), so

```
vga_index = group * 16 + nibble        group = (word 3 >> 4) & 0x0f
```

**The group is in word 3, not word 0.** Word 0 was wrongly read as the group for a while
because its low byte is constant at 16 and its high byte happens to span 0..15; that model
survived until a portrait disproved it. `buste.io`'s 33 portraits all carry
`word0 = 0x0010` -- so word 0 would put every one of them in group 0, which renders them
as green faces -- while their `word3` values are `0x60, 0x70, 0x80 ... 0xd0`, exactly
`group * 16`, and the portrait at 14802 is legible only at group 6 = `0x60 >> 4`.

Word 3's **low nibble is a per-sprite index**, which is what the live capture's
`0xa2, 0xa3, 0xa4, 0xa5` on four shrinking sprites meant: group 10, distance steps 2 to 5.

Word 0 is `flags | colour-count` after all (3.10, T11q): low byte 16 for 742 of ~800
sprites, high nibble `0x00`/`0x10`/`0x20`.

Header word 0 was the last unexplained field, and its high byte is the group: the
values read live were `0x0012, 0x0017, 0x0310, 0x070f, 0x0b00, 0x0c14, 0x0e10` --
a group index in the high byte and a small low byte. Rendering everything as group 0
is what left the shapes right and the colours wrong.

**Independent confirmation of the palette work:** reading the framebuffer at `0xA0000`
over GDB and rendering it with the palette recovered from `fond.io` reproduces the game
screen exactly, colours included (`captures/t11m2-vram.png` against
`captures/t11m2-state.png`). That validates 3.9 end to end -- the file's 768 bytes really
are the DAC the game is running.

**Status:** confirmed by rendering. Taking the group from word 3 turns the whole
extraction legible -- skin tones, silver armour, a wooden cabinet, stained glass -- where
word 0 gave green faces. A pixel-exact framebuffer comparison is still outstanding
(T11m), but the model now has a falsification test it passed and a competing one it
failed.


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

#### Palette records carry a 4-byte header (T11m4)

A palette in a file is not loose bytes: it is a record.

```
fe ff 00 00        4-byte marker
<768 bytes>        256 entries of 8-bit R,G,B
```

so a bank record is **772 bytes**. Searching for `fe ff 00 00` enumerates palettes from
the file's structure rather than from its content -- **but the marker alone is not
sufficient**: the sequence occurs freely inside pixel data, and of 80 raw hits across the
game only **17 are palettes**. Each candidate has to be confirmed against the independent
white/black group signature. Taking the marker on its own would have handed 20 assets a
palette made of picture bytes, with nothing to show it was wrong except the colours. That recovers
exactly the offsets established independently against the live DAC -- `geren.io` 6684,
`fond.io` 12108, `ftemple.io` 16244, `frise.io` 34700, `fcave.io` 1310 -- and it settles
the count: **`geren.io` holds 7 palettes, not the 12 a white/black signature scan
reported.** The five extras each sat exactly 48 bytes -- one palette group -- before a
real one, which is the signature repeating rather than a second palette.

Strides between records are a uniform 772 apart from one 1,724 gap in `geren.io`, so
something else is stored between two of the records there.

| asset | palettes |
|---|---|
| `geren.io` | 7 (6684, 7456, 9180, 9952, 10724, 11496, 12268) |
| total | **17 palettes across 9 assets** |
| `gerdep.io` | 3 |
| `itaverne.io` | 2 |
| `fond.io`, `fcave.io`, `fcave2.io`, `ftemple.io`, `fville.io`, `frise.io` | 1 each |

**`logo.io` is the exception**: its palette at 992 is verified byte-for-byte against the
framebuffer yet carries no marker, while an identical copy at 20172 does. That fits the
rest of what makes `logo.io` odd -- it is the 8bpp asset (3.10) and does not go through
the 4bpp path.

**Verified by:** the marker scan reproduces every palette offset previously established
by matching the emulator's DAC, and `tools/ioscan.py` now uses it -- which also corrected
`geren.io`, where the old heuristic picked 12268 over the verified 6684.

### 3.11 The nine assets that are not compressed (T11g)

The container census over all 106 files, by `hdr_mode`:

| mode | files | status |
|---|---|---|
| `0xa100` | 88 | bit-packed LZ, decodes |
| `0xa101` | 6 | decodes |
| `0xa102` | 3 | decodes |
| `0x0000` | 5 | one is stored, four are not containers |
| `0x0204`, `0x03cc`, `0xcdcd` | 4 | not containers |

**`blancpc.io` is mode 0 = stored.** Its `hdr_size` of 2100 equals the file length, so
`out_len` is 2094 and the payload is exactly 2094 bytes -- the decoder now copies it and
reports **zero bytes left over**, which is the byte-for-byte check. It failed before
because `stride_for()` had no case for mode 0 and defaulted to eight RLE passes,
producing "input exhausted in pass 7".

**The other eight are `.fic` files and are not containers at all.** Their first six bytes
are data being misread as a header -- `cont1.fic` claims a size of 0, `cont3.fic` claims
52,736 in a 4,860-byte file. The evidence that they are raw:

- **`cont1` through `cont6` are all exactly 4,860 bytes.** Compressed files do not come
  out the same length six times.
- `0xcd` and `0xcc` are among the most common bytes in five of them -- the MSC
  uninitialised-memory fill, so these were written from a partly-filled buffer.
- `tab1.fic` (361 bytes) contains only the values 1, 2, 3 and 4: a lookup table.
- `cont6.fic` is 97% zeros with 8 distinct values; `en1.fic` is 68% zeros.
- All eight are named in `main.io`'s catalogue, and **none of their names appears in the
  executable**, so they are addressed as data through the catalogue rather than opened by
  name from code.

**Lead, not a claim:** `cont` files are equal-sized grids of small integers with
uninitialised padding, which is the shape of map data -- and Ishar's world is a set of
regions. 4,860 factors as 81x60 or 54x90. See T11g2.

**Verified by:** the mode census over all 106 files; `blancpc.io` decoding to exactly its
declared length with no residue; byte histograms and the catalogue/executable name search.

### 3.12 `cont*.fic` are the world maps (T11g2)

Six files, each **exactly 4,860 bytes**, holding a **90 x 54 grid of one byte per cell**.

The width was measured, not guessed: byte autocorrelation over `cont1`, `cont3` and
`cont5` peaks at **lag 90**, with 180, 270 and 360 following -- the signature of a row
stride. 4,860 / 90 = 54 rows.

Rendered at that geometry the files are unmistakably maps (`captures/t11g2-cont-grids.png`):
closed coastlines, landmasses, a walled settlement in the middle of `cont2`, and a large
built structure filling most of `cont5`. `cont6` is almost empty -- 4,722 of 4,860 cells
are zero -- with a single horizontal run, so it is either unfinished or a special area.

What is known about the cell values:

| value | meaning |
|---|---|
| `0x00` | empty / open. 26-97% of each grid |
| `0xCE` (206) | **the boundary outline.** Present in all six, and each cell has a mean of 1.96-1.99 orthogonal neighbours of the same value -- what a one-cell-wide closed curve gives and nothing else does |
| `0xCC`, `0xCD` | outside the playable area. The MSC uninitialised-memory fill, so the grid was written from a partly-filled buffer |
| `0x9D` (157) | common and partly line-like; walls or paths, not established |
| others | 53-91 distinct values per file: terrain and object types, not yet decoded |

**`map.io` is not the same thing.** It decodes normally and autocorrelates at lag 160 --
160 bytes per row is 320 pixels at 4bpp -- so it is the rendered map *picture* shown to
the player, not the grid the game walks on.

**Verified by:** autocorrelation over three files independently agreeing on 90; the
rendering itself; and the neighbour-count test that isolates `0xCE` as an outline in all
six files.

## 7. Scripts are stored in `.io` assets (T27, partial)

`main.io` is not a catalogue in the sense of a table. It is **bytecode for the VM of
section 6**, and opcode `0x45` proves it. Its handler, `vm_op_load_asset` at
`seg_0000:2dbd`:

```
call 1624
lodsw                  ; a word asset id
test ax,ax / jz ...
mov  ss:[0b04], ax     ; store the id
mov  dx, si            ; DX -> the filename, inline in the script
call load_asset_by_name (78f9)
lodsb / cmp ax,0 / jnz ; skip past the NUL-terminated name
ret
```

which is exactly the shape seen in the decoded bytes of `main.io`:

```
45  40 00  "logo.IO" 00
^   ^      ^
|   |      inline NUL-terminated name, skipped by the handler
|   asset id 0x0040 = 64, which is logo.IO's catalogue id (3.5)
opcode 0x45
```

So an asset id and its filename are **operands of a script instruction**, not rows of a
table, and the "catalogue" is a program that loads the game's assets. That also explains
why `.fic` filenames appear in `main.io` and nowhere in the executable (3.11): nothing in
the code names them, a script does.

**Confirmed live.** Breaking on the interpreter's fetch (`seg_0000:69ab`) while the game
runs and reading `DS:SI` gives `1cf3:144e`, `1cf3:0cc6`, `1cf3:0cc7`, `1cf3:0cca` -- and
those bytes are found **in decoded `main.io` at offsets 5198, 3270, 3271 and 3274**. SI
advancing 3270 -> 3271 -> 3274 is a program counter stepping through instructions of
different lengths.

So the script the game is executing during play *is* `main.io`, held in its decode buffer
at segment `1cf3`. Scripts are stored in `.io` assets, decompressed by the normal
container path (section 3), and executed in place.

**Verified by:** the handler read from `ishar-listing.txt` against the byte pattern in
decoded `main.io`, with the asset id matching the catalogue id independently established
in 3.5.

### 7.3 A single-table disassembler cannot get `main.io`'s lengths right (T38b)

`tools/vmdis.py` decodes every byte of `main.io` through the **statement** table at image
`0x24`. That is wrong for a large minority of instructions, and it is why the listing
drifts out of alignment in places.

**79 of the 230 statement opcodes call the expression evaluator** (`seg_0000:69a6`) inside
their handler. The bytes that follow such a statement are not statement opcodes: they are
**expression** bytecode, dispatched through the *byte-scaled* table at `0x01f2` (section
6), which is a different instruction set with different operand widths. A statement's
length is therefore **variable** -- it depends on how the nested expression parses -- and
no fixed per-opcode width can express it.

That is the real content of the "97% decoded as instructions" figure: with 219 of 231 byte
values valid as statement opcodes, a single-table linear walk always resyncs and always
scores ~97%, whether or not it is reading the right table.

**Worked example.** The disputed region at payload offsets 96-160 is a run of nine 5-byte
`0x29` records, and it resumes on exactly the two offsets the running VM reported as
instruction boundaries:

```
 96: 29 80 00 01 01
101: 5a 00              <- two bytes, not the three vmdis assigns
103: 29 82 13 00 01
...
143: 29 68 15 01 02
148: 1a 00              <- two bytes
150: 29 ec 15 00 02
```

`0x5a`'s handler is `mov ss:[0c76],0 / call 69a6 / ... / lodsw`, so it consumes a nested
expression *before* its own word. The drumbeat of `0x29` records is independent
corroboration that 103 and 150 are right and the listing is wrong there.

**Consequence:** a correct `main.io` listing needs an interpreter, not a table -- the
lengths only fall out of actually evaluating the nesting. That is T39, and it is now the
prerequisite for T30 rather than a nice-to-have.

**Verified by:** handler scan bounded at each `ret` and at the next handler start (79 of
230); the byte dump above; live `DS:SI` samples at `vm_run` (FINDINGS 4.14).

#### Five sprite formats, selected by word 0's low byte

| mode | header | pixels | palette base | routine |
|---|---|---|---|---|
| `0x00` | **6 bytes** | 4bpp | **zero** | `seg_0e97:0b40` |
| `0x10` | 8 bytes | 4bpp | word 3 low byte | `seg_0e97:0b4c` -- 742 of ~800 sprites |
| `0x12` | 8 bytes | 4bpp | word 3 low byte | `seg_0e97:0aca` |
| `0x14` | 8 bytes | **8bpp**, index 0 transparent | n/a | `seg_0e97:0a84` (`lodsb/test/stosb`) |
| `0x16` | 8 bytes | **8bpp opaque** | n/a | `seg_0e97:0a5b` (`rep movsw`) |

This retires `logo.io`'s status as an exception. Its sprite at 1856 carries
`word0 = 0x0714`, so **mode `0x14`, 8bpp with index 0 transparent** -- exactly what the
byte-for-byte framebuffer comparison in 3.7 measured, including the 4,117 transparent
zeros. It was never a special case; the mode byte said so all along and was being read as
a colour count.

Teaching `tools/ioscan.py` the table took the extraction from **786 sprites to 920**, and
`logo.io` now yields its verified 144x118 sprite at the right geometry. Files that lost
sprites were ones that should not have had them: `geren.io` (the palette bank),
`message*.io` (text), `map.io` (a picture, not a chain), `blancpc.io` (raw data).

#### Reading a chain out of a file that is not sprites (T11s)

A chain walk finds sprite headers wherever the bytes happen to look like one, so a file
that is *not* a sprite bank still yields a chain. `main.io` is a script (section 7) and
produced 37 "sprites", 36 of them slivers of about 80 pixels -- bytecode read as headers.

Chain coverage looks like the discriminator and is not: `main.io` explains 9% of its file
against `buste.io`'s 95%, but `objet.io` sits at 13% with 21 genuine sprites, so cutting
on coverage destroys real data. **Area separates cleanly.** A minimum of 150 pixels
removes every sliver while keeping the smallest genuine sprites, and it must be applied to
the walk's *output* -- the chain still has to step across the slivers to stay in sync.

The 37th sprite in `main.io` is real and worth keeping: a **16x16 mouse cursor** at offset
25760.

#### The code that applies the palette base (T11r2)

`sprite_base_from_word3` (`seg_0e97:0b4c` for mode `0x10`, `seg_0e97:0aca` for `0x12`):

```
mov al, [si+6]      ; word 3's LOW BYTE
shr bx, 1 / add si, bx
add si, 8           ; past the header
mov bh, al          ; BH = palette base
...
lodsb / mov ah, al
shr al,1 x4         ; high nibble
add al, bh          ; + base
and ah, 0fh         ; low nibble
add ah, bh          ; + base
stosw               ; two 8-bit pixels
```

So the base is **word 3's low byte, added directly** -- and that byte is already
`group * 16` (`buste.io` carries `0x60` = group 6). The two readings agree; the machine
uses the byte, and `group = byte >> 4` is the human view.

**Word 0's low byte is a pixel-format selector, not a colour count.** `sprite_mode_dispatch`
(`seg_0e97:0a30`) switches on it over `0x10, 0x12, 0x14, 0x16, 0`. Mode `0x10` -- which
742 of ~800 sprites use -- and mode `0x12` both take the base from word 3 with an 8-byte
header. Mode `0x00` (`seg_0e97:0b40`) sets the base to **zero** and uses a **6-byte**
header instead.

**Verified by:** the instructions themselves. `add al, bh` with `bh` loaded from `[si+6]`
is a stronger statement than a pixel comparison, and it independently confirms T11r, which
was established by rendering alone.

### 7.5 `main.io`'s entry point is offset 24, and scripts are resumable (T39c)

The first entry to `vm_run` in an entire run has `DS:SI = 1cf3:0018`, which is
**`main.io` offset 24**. The first six entries are

```
24, 60, 96, 103, 108, 113
```

and `tools/vmi.py` stepping from 24 reproduces that sequence exactly. The first 24 bytes
are therefore **not script** -- which is why stepping from 0 dies after 23 statements at
offset 40.

**Scripts are resumable, not called.** The caller is `seg_0000:26af`, and the two
instructions around the call are the whole story:

```
lds  si, es:[bp-8]      ; restore the script's far program counter from the frame
call vm_run
mov  es:[bp-8], si      ; save it back
```

So a script's PC is a far pointer living in the frame at `es:[bp-8]`; `vm_run` runs until
a statement returns control and the updated `SI` is written back. That makes every script
a coroutine the engine resumes, and it means **the entry point is whatever was stored in
that slot**, not a constant in the code. Finding who first writes `es:[bp-8]` is the
general form of T37's question.

**The statements at 24 and 60 are both opcode `0x46`**, 36 bytes each -- `lodsw / lodsb /
mov cx,20h / rep movsb`, where the `rep movsb` takes 32 bytes of inline record straight
out of the script stream. Two entity declarations, then the block initialisers at 96.

**Verified by:** a breakpoint on `vm_run` from a paused start, catching the first six
entries ever; the 64-byte run at each `DS:SI` matched uniquely against `main.io` and
against no other asset; and the stepper reproducing all six offsets offline.

### 7.6 Assets other than `main.io` do run script (T37b)

T37's premise is that embedded scripts have no known entry point. Both halves of that can
now be improved on: three assets are **observed executing bytecode**, and two entry points
are known.

Method: break on `vm_run`, and match each `DS:SI` against the decoded assets requiring the
64-byte run to be unique **within** its asset and absent from **all 97 others**. In a
130s gameplay scan every sample was attributed, none ambiguous:

| asset | distinct PCs seen | range | size |
|---|---|---|---|
| `frise.io` | 60 | 478..32831 | 53,808 |
| `dplt.io` | 39 | 198..3285 | 3,376 |
| `main.io` | 34 | 3269..20140 | 26,384 |

`frise.io` is the UI frieze and `dplt.io` was unclassified; both run VM code. That turns
"the unexplained bytes are consistent with bytecode" (T37) into "these assets are running
bytecode", observed.

**Two entry points.** From a *paused cold start* the breakpoint catches every `vm_run`
entry in order, so the first offset seen for an asset is its entry. `main.io` enters at
**24** (7.5) and `logo.io` also enters at **24**.

**But 24 is not established as a universal entry**, and the obvious test says so. Stepping
`tools/vmi.py` from a given offset across all 98 assets gives:

| start | median statements | assets reaching 10 |
|---|---|---|
| 16 | 25.0 | 88 |
| 18 | 23.0 | 88 |
| **24** | **17.0** | **68** |
| 26 | 21.0 | 79 |

Offset 24 scores *worse* than its neighbours. With 219 of 231 byte values valid as
statement opcodes, any start decodes plausibly for a while, so this test cannot pick an
entry point -- the same trap as "97% decoded" (7.3). The only real evidence is the two
assets watched live.

**Status:** partial. The method for finding an entry point is settled and cheap (cold
start, first `vm_run` entry, strict matching). It has been run long enough to reach
`main.io` and `logo.io` only; `frise.io` and `dplt.io` were caught mid-execution, so their
lowest sampled offsets (478, 198) are **not** entry points.

**Verified by:** `.ish/t37b.json`; `tools/t37b-scan.py`; the rival-offset table above.

### 7.4 Some statements are variable-length, and that is what broke the listing (T39)

Opcode `0x29` (handler `seg_0000:5713`) is a **block initialiser** whose length depends on
its own operands:

```
lodsw            ; destination offset
lodsb            ; cx = count
lodsb            ; one byte stored
inc cx
jmp .test
.body: lodsw     ; one further WORD from the stream per iteration
.test: sub di,2 / loop .body
```

`loop` decrements before testing, so the body runs `count` times and the instruction is
**`5 + 2*count` bytes**.

This resolves the two disagreements T38 found between the listing and the running VM, and
it resolves them exactly:

| at | bytes | count | body swallows | next |
|---|---|---|---|---|
| 96 | `29 80 00 01 01` | 1 | `5a 00` | **103** |
| 143 | `29 68 15 01 02` | 1 | `1a 00` | **150** |

103 and 150 are precisely the offsets the live VM reported as instruction boundaries.
The `5a` and `1a` that `vmdis` was decoding as statements are **operand data inside the
preceding instruction**, not opcodes at all -- which is why no adjustment to `0x5a`'s or
`0x1a`'s operand width could ever have fixed it.

**Two consequences.**

*No table can describe this format.* An instruction whose length is read from its own
operand stream cannot have a per-opcode width, so `tools/vmdis.py` is unfixable in kind,
not merely in detail. `tools/vmi.py` steps instead, and reproduces the whole run of nine
`0x29` records including both disputed boundaries.

*Deriving widths from the listing automatically is not enough.* `walk()` reads a handler's
`lodsb`/`lodsw` in order and gave `0x29` the signature `w,b,b,w` -- it saw the loop body's
`lodsw` once and counted it as a fixed operand. The handler has to be *read*, not scanned.

**Status:** partial. `tools/vmi.py` walks 138 statements from offset 96 before meeting an
opcode it cannot size, and offset 0 is **not** a valid entry point -- stepping from it dies
after 23 statements at offset 40. Every handler modelled so far is listed in the file.

**Verified by:** the handler at `seg_0000:5713` read instruction by instruction; the
stepper reproducing offsets 96 -> 103 -> ... -> 143 -> 150 -> 155; and live `DS:SI` samples
at `vm_run` naming 103 and 150 independently (FINDINGS 4.14).

### 7.1 Disassembling a script (T30)

`tools/vmdis.py` decodes a script with a table built from the handlers themselves: the
statement table at image `0x24` gives each opcode's routine, and the routine's own
`lodsb`/`lodsw` sequence gives its operand widths. Nothing is guessed.

**The check that matters is not the percentage decoded.** 219 of 231 byte values are valid
table entries, so a linear walk "decodes" noise as readily as code and reports 98%
regardless. The real check is the live program counter: the interpreter was caught at
`SI = 3270, 3271, 3274` and `5198` (section 7), and disassembling from 3270 produces
instruction boundaries at **exactly those offsets**. The operand lengths are right because
the CPU agrees with them.

`main.io` starts with data, not code -- disassembly from offset 0 is noise. Execution runs
in the region the live samples came from.

**What the listing shows.** 101 clean `vm_op_load_asset` instructions, each an asset id and
a filename, grouped in runs:

| offset | what loads together |
|---|---|
| 1540 | `presen`, `preson`, `presti` -- the presentation screens |
| 2812 | `geren` (**the palette bank**), `affobj`, `encont`, `dplt`, `message*`, `sos*` |
| 6115 | `rplaine`, `inville`, `temple`, `telep`, `mcave`, `ville`, `pabo` -- places |
| 8508 | `orc`, `bormin`, `kiriela`, `loup`, `azal`, `wardog`, `barbare`, `wiz1`, `naim`, `morgu`, `dealer`, `sorcier`, `predator`, `momo` |
| 10253 | `spider`, `geant`, `skelet`, `spectre`, `dragon`, `medus`, `goul`, `darkm`, `darkwiz`, `gaz`, `zombi`, `dwarrior`, `knight` |
| 11386 | `village`, `incave`, `intmais`, `stage`, `taverne`, `marchand`, `saub`, `buste` |
| 12708 | `boishar`, `dead`, `theend` -- the endgame |

The palette bank loading early with the common set fits it being global rather than
per-scene (3.9).

**Known limitation.** The walk drifts by a byte in places -- `temple.IO` comes out as
`emple.IO`, and a handful of "loads" carry nonsense names -- so at least one opcode's
operand length is still wrong. Names that do not match `[A-Za-z0-9_]{2,11}\.(IO|FIC)` are
where it is out of step, which makes the drift self-locating.

**Verified by:** instruction boundaries reproducing four independently captured live
program counters, and 101 decoded filenames matching real assets on disk.

#### Operand lengths, and the trap in deriving them (T30b)

Reading each handler's `lodsb`/`lodsw` sequence gives operand widths, but a handler whose
`ret` is not decoded in the listing is walked straight *out of*, into the next routine,
whose own `lodsb` is then counted as an operand. Five opcodes came out **exactly one byte
too long** that way -- `0x00` (a no-op, given one operand), `0x4f`, `0x1d`, `0x70`, `0x78`.

Every handler start is known from the table, so stopping the scan on reaching one fixes it.
The effect is large: of 219 places in `main.io` where a valid `45 <id> "name\0"` sits, the
walk landed on **96 before the fix and 217 after**, with the four live program-counter
boundaries still reproduced.

**The 2 sites still missed, and 18 decodes with non-filenames, are not drift:**

- **Names the game constructs.** The script asks for `boishar.IO`, `taverne.IO` and
  `tableau.IO`; the disk holds `iboishar.io` and `itaverne.io`. A letter is prepended at
  load time -- the same mechanism as the language suffixes on `message*.io` and `textin*.io`.
- **French prompts sitting in the script**: `" DE CONTREE ?"`, `" DE REGION ?"`,
  `" DE ZONE ?"`, `"TER TABLEAU ?"` -- fragments of questions like *"ENTRER TABLEAU ?"*,
  i.e. developer or level-editor text left in the shipped file.
- **A data region** around offsets 17205-20193 that is not code at all.

### 7.2 What else is inside `main.io` (T30c)

Beyond the asset-loading program, `main.io` carries text and data that a linear
disassembly walks into. Byte ranges, from a scan for printable runs:

| range | contents |
|---|---|
| 2313-2698 | **level-editor prompts** (below) |
| 16620-16827 | `main.co`, `main.ao`, `foret.co`, `foret.ao` -- extensions that exist nowhere on disk |
| 17046-17172 | `"  DISK A"` .. `"  DISK D"` -- disk-swap prompts, matching the drive-select `int 21h ah=0eh` in `load_asset_by_name`'s path |
| 17299-17396 | `"1 - ENGLISH"`, `"2 - FRANCAIS"`, `"3 - DEUTSCH"`, `"4 - ITALIANO"` -- **the language menu** |
| 19954-19990 | `"PROG :"`, `" VAR :"`, `" SPT :"` -- a memory-usage display |
| 20200-21180 | binary data, high-entropy, not code |

#### The level editor left in the shipped game

```
POSITION X :
POSITION Y :
NUMERO DE CONTREE ?
NUMERO DE REGION ?
NUMERO DE ZONE ?
EDITER TABLEAU ?
```

These name **the world's hierarchy in the developers' own words**: *contrée* (region/land),
*région*, *zone*, *tableau* (screen/board), addressed by X/Y position. `cont1.fic` ...
`cont6.fic` are **contrées** -- six of them, one file each (3.12) -- which turns T11g3 from
guesswork into filling in a named structure. `PROG:/VAR:/SPT:` alongside is a memory
display, so this is a development build's tooling, shipped.

#### Names the game asks for that are not on disk

The script requests `boishar.IO`, `taverne.IO` and `tableau.IO`. The bytes are literal --
`45 3d 00 "boishar.IO" 00` -- so this is not a disassembly artefact. The disk holds
`iboishar.io` and `itaverne.io`, and no `tableau.io` at all.

`tableau.io` is presumably the editor's own file, absent from the release. For the other
two the loader must prepend a letter; `intmais.io`, `inville.io` and `incave.io` suggest
`i` for *intérieur*, but that is a reading of the names, **not a measurement**, and the
rule is not established. The test is one breakpoint: `load_asset_by_name` builds the name
into a buffer at `ss:2480` before opening it, so breaking on the DOS open and reading that
buffer gives the name actually requested.

### 3.13 Transparency belongs to one mode, not to the format (T11m2)

**4bpp sprites are opaque.** `expand_4bpp` (`seg_0e97:0ad1`) splits each byte and writes
both nibbles with `stosw`, with no test for zero:

```
lodsb / mov ah,al / shr al,1 x4 / add al,bh / and ah,0fh / add ah,bh / stosw
```

Only **mode `0x14`** skips zeros -- `seg_0e97:0a84` is `lodsb / test al,al / jz / stosb` --
and mode `0x16` is `rep movsw`, opaque as well.

This was got wrong for a long time. Index 0 was established as transparent from
`logo.io`'s sprite at 1856, where 4,117 pixels decoded as 0 against a background of 5 in
the framebuffer (3.7). That sprite is **mode `0x14`**, the one mode where it is true, and
the rule was generalised to the whole format. Every 4bpp sprite was rendered with holes
punched through it wherever a pixel used colour 0 -- which reads as green speckle scattered
through otherwise correct art, and is easy to mistake for a palette fault.

**Status:** the framebuffer check has now been done, and it contradicts the code above
for mode `0x10`. See 3.13b.

### 3.13b The framebuffer says mode `0x10` keys nibble 0 (T36b)

`buste.io`'s portrait -- the sprite at 6986, mode `0x10`, 64x36, `word3 = 0x00d0` -- was
compared pixel by pixel against live VRAM with the party panel on screen, at its measured
origin (screen 0,147):

| | |
|---|---|
| nibble != 0 | **1233 / 1233 identical = 100.0000%** |
| nibble == 0 | 1071 pixels, **0 identical** |

Every drawn pixel is exactly right, and every nibble-0 pixel shows something else: values
177-181, which is `frise.io`'s base 176 -- the frieze *behind* the portrait. So nibble 0
was not written. `frise.io`'s own sprite at 42656 behaves the same way (172 nibble-0
pixels, none matching).

Two things follow.

**The rule is on the nibble, not the palette index.** Key when the **nibble** is 0, before
the group base is added -- not when the final index is 0. Those are different tests: with
base 208 the final index is 208, never 0, so a test on the index can never fire. That
distinction is what makes this compatible with 3.13's history: keying on the *index* was
indeed wrong and produced the speckle, and keying on the *nibble* is what the machine does.

**`expand_4bpp` at `seg_0e97:0ad1` is not the routine that drew this.** It writes both
nibbles with `stosw` and tests nothing, so it cannot produce the result above. There is
another 4bpp expander -- a masked one -- and 3.13 describes a real routine that is not the
one in use here. That is the scar in `CLAUDE.md` ("a routine you found by reading is not
the routine in use") landing on this file. Finding it is T36c.

### 3.13c The complete transparency table, from the dispatcher (T36c)

`sprite_mode_dispatch` (`seg_0e97:0a30`) routes each mode to its own expander, and the
five differ. Read from the code, and now consistent with the framebuffer:

| mode | bpp | header | base | transparency | route |
|---|---|---|---|---|---|
| `0x00` | 4 | 6 | forced 0 | **nibble 0 keyed** | `0b40` -> `jmp 0b58` -> masked loop |
| `0x10` | 4 | 8 | `[si+6]` | **nibble 0 keyed** | `0b4c` -> falls to `0b58` -> masked loop |
| `0x12` | 4 | 8 | `[si+6]` | opaque | `0aca` -> falls into `expand_4bpp_opaque` |
| `0x14` | 8 | 8 | 0 | index 0 keyed | `0a84`: `lodsb / test al,al / jz / stosb` |
| `0x16` | 8 | 8 | 0 | opaque | `0a5b`: `rep movsw` |

The masked loop is `expand_4bpp_masked` (`seg_0e97:0b63`):

```
lodsb / mov ah,al / shr ah,1 x4 / test ah,ah / jz +7 / add ah,bh / mov es:[di],ah
inc di / and al,0fh / jz .. / add al,bh / stosb / loop
```

`test` before `add`: the key is on the **nibble**, never on the final index. Skipping is
`inc di`, so the pixel already on screen survives.

Modes `0x00` and `0x10` share the loop, so **mode `0x00` is keyed too** -- which means the
old "holes in `presti.io`'s letters" were the *correct* behaviour for a mode `0x00` asset
(base 0, so `index == 0` and `nibble == 0` coincide there), and making it opaque replaced
real transparency with `palette[0]`. Both readings of that bug were half right: keying the
*index* is wrong for `0x10` and right for `0x00`; keying the *nibble* is right for both.

**The base is `word3`'s low byte used directly** (`mov al,[si+6]` / `mov bh,al`), added to
each nibble -- not `(word3 >> 4) * 16`. The two agree only because that byte's low nibble
is always zero in the shipped assets.

`expand_4bpp_opaque` (`seg_0e97:0ad1`) never fires during gameplay: 0 hits in 20s of
walking, against 5 for a control at `seg_0000:93a6`.

**Consequence for the extracted art:** anything rendered with 4bpp treated as opaque had a
solid rectangle of `base + 0` where transparency belongs. `tools/ioscan.py` now keys the
nibble and `tools/png.py` writes RGBA, so `captures/assets/` carries real alpha instead of
a sentinel colour (T36d). Re-extracted: 803 PNGs, all RGBA. The verified case,
`buste.io`'s portrait, comes out with **1071 alpha-zero pixels** -- exactly the count the
VRAM comparison predicted -- and its **1233 opaque pixels still match VRAM 1:1**.

**Verified by:** live VRAM at `0xA0000` with the game in Dragonia, compared against the
payload from a decoder written only from this file; the sprite's `word3 = 0x00d0` predicts
group 13 / base 208, which is also the base an independent reverse search recovered from
the screen bytes without being told it.

### 3.13d The viewport has its own expanders, and "scaling" is a per-row step (T11p)

The 3D view is not drawn by the sprite path in 3.13c. It has its own family in
`seg_0e97`, found by breaking on writes to the **e000 back buffer** while turning on the
spot -- 16 hits at each of two sites, against a control that produced 0 there:

| | |
|---|---|
| `viewport_row_loop` `seg_0e97:05c0` | per-row loop; `and bh,bh / je` picks masked or not |
| `viewport_expand_4bpp` `seg_0e97:0644` | high nibble, `add al,bl`, `stosb`, then low nibble -- **no zero test, opaque** |
| `viewport_expand_4bpp_mirrored` `seg_0e97:05e5` | right-to-left (`dec di`, `es:[di-1]`) and **does** test zero |
| `viewport_fill_rect` `seg_0e97:06d5` | `rep stosb / add di,bx / dec bp / jnz` -- sky and ground bands |

So there are now **five** 4bpp expanders in the game, not one: the panel's masked
(`0b63`), the panel's opaque (`0ad1`), and these three. All use the same nibble order and
`base + nibble`; they differ in direction and in whether zero is skipped.

**The "scale" is not a resample.** `viewport_row_loop` ends with

```
add si, cs:[002c]        ; source advance per row
add di, cs:[002e]        ; destination advance per row
```

Two independent per-row deltas. Sampled live while walking in Dragonia: `cs:[002c] = 15`,
`cs:[002e] = 321`. A destination step of **321 on a 320-wide buffer shifts every row one
pixel sideways** -- a shear, which is where the perspective comes from; the source step
chooses how fast the sprite is consumed, which is where the size change comes from.

This is why T36's framebuffer search found **no** asset matching the viewport at either
depth over 1,517 probe runs while the UI panel matched immediately: viewport pixels are
sheared and row-skipped, so they cannot appear verbatim anywhere.

**Verified by:** MEMORY_WRITE breakpoints on `0xE0000 + y*320 + x` with a control
breakpoint on never-written memory to subtract the phantom stops; instruction text read
from the emulator, which had executed the region the listing still had as `db`.

### 3.14 `presti.io` -- unresolved

The title lettering. Nine sprites, all **mode `0x00`** (6-byte header, and the code at
`seg_0e97:0b40` sets the palette base to **zero**). What is measured:

- 80% of its pixels use indices 7-10, so the palette needs a smooth ramp there.
- At base 0 with any scene palette the letters come out mottled green/brown/blue --
  `fond`'s group 0 puts unrelated colours at 7-10.
- With **`logo.io`'s palette at 992 and a base of 16** the letters render as a clean
  bronze ramp. `logo`'s group 1 is `620 730 830 840` at those indices.
- No stored palette has that ramp at group 0 (nearest is 65 per channel), and the
  executable contains no palette-shaped block that fits either.

**So the rendering is empirical, not derived**: the code says base 0 and the picture says
base 16, and that contradiction is unexplained. The background also comes out white,
because index 0 then lands on palette entry 16, which is white -- either these sprites are
composited over something that makes that correct, or mode `0x00` keys index 0 somewhere
not yet found.

`tools/ioscan.py` carries this as an explicit `INDEX_SHIFT` exception so the extraction is
usable while the reason stays open. **It should not be read as understood.**

## 8. `affobj.io`, byte by byte

730 bytes on disk, 1432 after decoding. Asset **id 7**. The name reads as *affichage
objet* -- object display.

### 8.1 The file on disk (730 bytes)

| offset | bytes | field | value | meaning |
|---|---|---|---|---|
| 0 | `9e 05` | `hdr_size` | 1438 | decoded length **including** this 6-byte header, so the payload expands to 1432 |
| 2 | `00 a1` | `hdr_mode` | `0xa100` | high byte `0xa0` after the `& 0xfe` mask -> the bit-packed LZ77 decoder at `seg_0000:7b85` (3.0, 3.2) |
| 4 | `01 00` | `hdr_is_catalogue` | 1 | non-zero, so **no** 16-byte directory follows; the payload starts at offset 6 |
| 6..729 | 724 bytes | payload | | LZ77 stream: an 8-byte offset-width table, then MSB-first bit codes (3.2) |

Every byte of the file is therefore accounted for: 6 of header, 724 of compressed stream.

### 8.2 The 1432 decoded bytes

**What they are not**, each ruled out by measurement rather than by eye:

- **Not a sprite bank.** The chain walk finds no valid sprite record (3.10); it is one of
  the 20 assets with no sprites at all (3.6).
- **Not a palette.** No `fe ff 00 00` record, and no 768-byte run passes the white/black
  group signature (3.9).
- **Not a fixed-record table.** 1432 factors as 8 x 179, but split into 8-byte records all
  eight byte positions have the *same* distribution -- 50 to 61 distinct values each, all
  peaking on `0x00`, `0x14`, `0x1e`. A record table has different fields in different
  columns; this has none.
- **Not text.** Only short printable runs, and its byte distribution is far from
  `textine.io`'s (cosine 0.64).
- **No repeating structure at all**: autocorrelation over lags 1-120 peaks at 0.149,
  against 0.47 for a real grid like `cont1.fic` (3.12).

**What they are: VM bytecode.** Three independent signals:

1. Its byte-frequency distribution is closest to `main.io`'s **verified code region** --
   cosine 0.83, against 0.68 for `main.io`'s own data region, 0.79 for sprite pixels and
   0.64 for text. Code and data *within* `main.io` sit at 0.72, so 0.83 is above the
   spread that separates them.
2. Its commonest bytes are `0x00, 0x14, 0x1e, 0x3a, 0x38, 0x2c, 0x1f, 0x12` -- the VM's
   language-core opcodes, the same set that dominates the call-count diff while the party
   moves (FINDINGS 6.3).
3. Scripts are stored in `.io` assets and executed in place (section 7), and this asset is
   loaded by the same `vm_op_load_asset` instruction as everything else -- `main.io` offset
   2824, `45 07 00 "affobj.IO" 00`, immediately after `geren.IO` and before `encont.IO`
   and `dplt.IO`, the common startup set.

### 8.3 What is *not* established -- read this before using the above

**Byte-by-byte meaning of the payload cannot be given yet, and this section does not give
it.** Disassembling requires an entry point, and:

- Every start offset from 0 to 79 scores identically under `main.io`'s opcode profile
  (0.109 to 0.110), so the alignment cannot be chosen that way. 219 of 231 byte values are
  valid opcodes, which makes "it disassembles" true of any alignment and therefore worthless
  as evidence (7.1).
- Sampling the interpreter's program counter 20 times during play put `DS:SI` inside
  `main.io` every time and never inside `affobj.io`, so its entry point was not observed.
  That is consistent with a script run only when an object is displayed.
- `main.io` itself begins with data and its code starts around offset 3270 (section 7), so
  offset 0 is not a safe assumption here either.

A listing from offset 0 is therefore **not** included, because it would be indistinguishable
from a listing of the wrong alignment. See T33.

**Verified by:** the header fields against `tools/io.py`'s decode (1432 bytes out, zero
residue); the four negative results above each from the tool that would have found the
structure; the distribution comparison against regions of `main.io` whose status is
independently known.

## 9. `zombi.io`, byte by byte — and how to write a reader

7,868 bytes on disk, 11,272 decoded. Asset **id 75 (`0x4b`)**. A monster sprite bank: the
zombie's 21 animation frames.

### 9.1 The file on disk (7,868 bytes)

| offset | size | field | value here | meaning |
|---|---|---|---|---|
| 0 | 2 | `hdr_size` | 11278 | decoded length **including** this 6-byte header |
| 2 | 2 | `hdr_mode` | `0xa100` | `(mode >> 8) & 0xfe` = `0xa0` -> bit-packed LZ77 (3.0, 3.2) |
| 4 | 2 | `hdr_is_catalogue` | 1 | non-zero, so no 16-byte directory follows |
| 6 | 7862 | payload | | LZ77 stream -> 11,272 bytes |

`hdr_size - 6` is exactly the decoded length, which is the check that the decode worked.

### 9.2 The decoded 11,272 bytes

| range | size | contents |
|---|---|---|
| 0..15 | 16 | asset header |
| 16..1949 | 1934 | **unidentified** |
| 1950..7685 | 5736 | **the sprite chain** — 21 sprites |
| 7686..11271 | 3586 | **unidentified** |

#### The 16-byte asset header

Every decoded asset opens with one, and it is a **general** part of the container, not
something peculiar to this file -- see **3.15**. For `zombi.io` it reads:

| offset | size | value | meaning |
|---|---|---|---|
| 0 | 2 | `0x004b` | asset id, 75 |
| 2 | 6 | `16 00 00 17 00 00` | format signature |
| 8 | 8 | `00 00 16 00 00 00 be 02` | not identified |

#### The sprite chain

Sprites are stored back to back with no gaps. Every one here is mode `0x10` and carries
`word3 = 0x0040`, so all 21 use **palette group 4** (`0x40 >> 4`).

| # | offset | size | word 0 | word 3 | record bytes |
|---|---|---|---|---|---|
| 0 | 1950 | 32x53 | `0x0010` | `0x0040` | 856 |
| 1 | 2806 | 80x27 | `0x0010` | `0x0040` | 1088 |
| 2 | 3894 | 16x30 | `0x0010` | `0x0040` | 248 |
| 3 | 4142 | 48x15 | `0x0010` | `0x0040` | 368 |
| 4 | 4510 | 16x21 | `0x0010` | `0x0040` | 176 |
| 5 | 4686 | 32x12 | `0x0010` | `0x0040` | 200 |
| 6 | 4886 | 16x21 | `0x0010` | `0x0040` | 176 |
| 7 | 5062 | 32x26 | `0x0910` | `0x0040` | 424 |
| 8 | 5486 | 32x15 | `0x0f10` | `0x0040` | 248 |
| 9 | 5734 | 32x19 | `0x0b10` | `0x0040` | 312 |
| 10 | 6046 | 16x12 | `0x0310` | `0x0040` | 104 |
| 11 | 6150 | 32x17 | `0x0d10` | `0x0040` | 280 |
| 12 | 6430 | 16x11 | `0x0510` | `0x0040` | 96 |
| 13 | 6526 | 16x19 | `0x0510` | `0x0040` | 160 |
| 14 | 6686 | 16x12 | `0x0810` | `0x0040` | 104 |
| 15 | 6790 | 16x17 | `0x0110` | `0x0040` | 144 |
| 16 | 6934 | 16x11 | `0x0710` | `0x0040` | 96 |
| 17 | 7030 | 16x17 | `0x0510` | `0x0040` | 144 |
| 18 | 7174 | 16x11 | `0x0910` | `0x0040` | 96 |
| 19 | 7270 | 32x19 | `0x0a10` | `0x0040` | 312 |
| 20 | 7582 | 16x12 | `0x0210` | `0x0040` | 104 |

The chain runs 1950 -> 7686 with **zero gap between records**, so `next = offset + record
size` is exact for this file.

### 9.3 Writing a reader

```
1  read the 6-byte file header
     hdr_size, hdr_mode, hdr_is_catalogue      (three little-endian words)
2  payload starts at 6, or at 22 when hdr_is_catalogue == 0 (a 16-byte directory follows)
3  decompress:  mode = (hdr_mode >> 8) & 0xfe
     0xa0 -> bit-packed LZ77          (97 of 106 files; 3.2)
     0x00 -> stored, copy verbatim    (blancpc.io only; 3.11)
     other -> byte-oriented RLE, stride = 1 for 0x80, else 8
   expect exactly hdr_size - 6 bytes out; anything else means the decode is wrong
4  decoded[0..1] is the asset id; decoded[2..7] should be 16 00 00 17 00 00
5  walk the sprite chain.  At a sprite record:
     word 0 = flags<<8 | mode      word 1 = width-1
     word 2 = height-1             word 3 = palette group * 16
     mode (word 0 & 0xff) decides the rest:
       0x00 -> header 6, 4bpp, palette base 0
       0x10 -> header 8, 4bpp, palette base = word 3 & 0xff
       0x12 -> header 8, 4bpp, palette base = word 3 & 0xff
       0x14 -> header 8, 8bpp, colour 0 transparent
       0x16 -> header 8, 8bpp, opaque
     stride = width for 8bpp, else (width + 1) / 2
     record = header + stride * height, and the next sprite begins right after
6  decode pixels.  4bpp is two per byte, HIGH nibble first, and is OPAQUE --
   only mode 0x14 treats index 0 as transparent (3.13)
     index = palette_base + nibble
7  colour it -- see 9.4, because zombi.io carries no palette of its own
```

**Finding the chain start is the part a reader cannot do naively.** It is at 1950 here and
nothing in the header points to it. `tools/ioscan.py` finds it by trying every offset and
keeping the one whose chain is longest, then dropping records under 150 pixels — bytecode
and pixel data both produce short bogus chains (T11s).

### 9.4 The palette

`zombi.io` contains no palette: no `fe ff 00 00` record and no 768-byte run that passes the
group signature (3.9). It borrows one, and every sprite in the file carries
`word3 = 0x0040`, so all 21 use **group 4** -- entries 64..79 of whichever 256-colour
palette is loaded.

The palette it borrows is **`fville.io`'s, the record at offset 1352** of that file's
decoded payload. That comes from `main.io`'s load order: a palette-carrying scene is loaded
and the assets drawn against it follow, and `zombi.io` follows `fville.io` (3.9, "Which
palette an asset borrows"). Group 4 of that palette is:

```
64: ff ff ff   65: 00 00 00   66: 33 13 00   67: 47 1f 07
68: 5b 2f 0b   69: 6f 3f 17   70: 83 4f 23   71: 97 67 2f
72: ab 7f 3f   73: 33 2b 1b   74: 4b 43 2b   75: 63 5b 3f
76: 7f 77 57   77: 97 93 73   78: af af 8f   79: cb cb b3
```

so a nibble of 6 in a zombi sprite is `33 13 00`, a nibble of 12 is `7f 77 57`, and so on.
Two browns ramps -- which is what a zombie should be.

**Status:** the pairing is inference from load order, not a measurement. It has not been
checked against the framebuffer, and 27 assets in the game follow more than one scene and
are resolved by majority (T11m2). For `zombi.io` the load order is unambiguous.


### 9.6 The spec, validated by an independent implementation

`java/IsharSprites.java` reads `zombi.io` and returns 21 bitmaps. It was written **only
from this document** -- no access to `tools/io.py` or `tools/ioscan.py` -- and its output is
**byte-identical to the reference extraction for all 21 sprites**, colours included.

That exercises 3.0 (container header), 3.2 (bit-packed LZ77, including reading zeros past
the end of the stream), 3.15 (the asset header, which reports id 75 as documented), 3.10
(sprite records and the mode table), 3.13 (4bpp opaque, high nibble first) and 9.4 (the
borrowed palette). Those sections are therefore implementable as written.

**Two things had to come from section 9 rather than from the general spec, and a reader
for an arbitrary asset would be stuck without them:**

1. **Where the sprite chain starts.** 1950 for `zombi.io`. Nothing in the container or
   asset header points to it, and 9.3 says as much -- the extractor finds it by trying every
   offset and keeping the longest chain. Any per-asset reader needs that search or a table.
2. **Which palette to borrow.** `fville.io`'s record at 1352, from load order (T11m2). The
   pairing for the other ~100 assets is not in this document; it lives in
   `.ish/asset-scene.json`.

So: the *format* is documented well enough to implement. The *per-asset facts* -- chain
start and palette source -- are documented for `zombi.io` only. See T35.

### 9.5 What is not known — 5,520 bytes, 49% of the file

Two regions are unidentified, and this section does not pretend otherwise.

**16..1949 (1,934 bytes).** Not sprites: no valid chain starts anywhere in it. Not a
palette: no record marker, no group signature. 425 zero bytes, 168 distinct values.

**7686..11271 (3,586 bytes).** Same negatives, plus one positive measurement: the byte
values are **symmetric about zero**. Counting small magnitudes, `+1..+16` occurs 818 times
and `-1..-16` (i.e. 240..255) occurs 822 — a ratio of 1.00. The sprite pixels in the same
file are 2.54 and the head is 1.51. Symmetric small signed bytes are what per-frame offsets
or movement deltas look like, which would suit an animation table for a monster with 21
frames — but that is a reading of a histogram, **not** a decode.

A distribution comparison against `main.io`'s known code was tried and is worthless here:
zombi's own *sprite pixels* score 0.86 against "code", higher than its head does. It cannot
tell code from pixels, so it says nothing about these regions — and by the same token the
0.83 that section 8.2 leans on for `affobj.io` is weaker evidence than it appears there.
See T34.

**Verified by:** header fields against `tools/io.py` (11,272 out, zero residue); the id
against `main.io`'s load instruction and across 94 assets; the chain walked with zero gaps;
the symmetry counts above.

## 10. Where the strings are, and their format

### 10.1 Which files

Text is not in one file per language; it is in **two sets of four**, one file per language:

| set | French | English | Deutsch | Italiano | strings | contents |
|---|---|---|---|---|---|---|
| messages | `message.io` | `messagee.io` | `messaged.io` | `messagei.io` | **99** | UI labels -- `LEVEL     : `, `EXPERIENCE: `, `AGILITY      : ` |
| narrative | `textin.io` | `textine.io` | `textind.io` | `textini.io` | **35** | the intro and story text |

The suffix is the language: **no suffix = French**, `e` = English, `d` = Deutsch,
`i` = Italiano. French carries no letter because it is the studio's own language and the
script's fall-through case (FINDINGS 6.8).

`sos.io`/`sosd`/`sose`/`sosi` follow the same naming but are **not text** -- they hold
filenames such as `foret.io`, `foret.co`, `foret.ao`.

**Confirmed live (T08).** Two cold boots traced to the first gameplay frame, one
selecting English and one French, open **33 files each and differ in exactly two**:

| | English run | French run |
|---|---|---|
| messages | `messagee.IO` | `message.IO` |
| filename table | `sose.IO` | `sos.IO` |
| everything else | identical, 31 files | identical, 31 files |

So the language choice changes the loaded set by two files and nothing else -- the
suffix scheme above is what the running game actually does, not just what the
directory listing suggests.

Two corrections that came out of the same diff:

- **`EN1.FIC` is not English.** It is loaded by *both* runs, so `EN` is not a
  language tag; it is a region/area file (`CONT1.FIC` and `TAB1.FIC` load beside
  it). It reads like a language code and is not one.
- **`textin*` is not loaded during boot at all.** Neither run opens `textin.io` or
  any variant on the way to the first gameplay frame, so the narrative set is
  pulled later, on demand. Only the `message*` and `sos*` sets are startup files.

**Verified by:** `.ish/t08-english-final.json` and `.ish/t08-french.json`, both
traced with `tools/gdbtrace.py --drive`, each ending in the Dragonia outdoor scene
(`captures/t08-english-gameplay.png`).

### 10.2 All four variants share one asset id

Every `message*.io` decodes with **asset id 14 (`0x0e`)** in word 0 of its payload
(3.15) -- the English, German and Italian files included, not just the French one. The same
holds for the other sets: `textin*` all carry `0x2f`, `sos*` all carry `0x56`.

The script asks for a **different** id per language, though. From `main.io`:

| file | id in the load instruction | id in the file's own header |
|---|---|---|
| `messagee.io` | `0x63` | `0x0e` |
| `messaged.io` | `0x64` | `0x0e` |
| `messagei.io` | `0x65` | `0x0e` |
| `message.io` | `0x0e` | `0x0e` |

So the header id names **what the content is** -- "the messages" -- while the script's id
names **which variant to fetch**. These nine language files are exactly the nine assets that
break the otherwise universal rule that the two ids match (3.15, 85 of 94).

### 10.3 The string encoding

Strings are **inline in the script**, not in a table with offsets. Each one is:

```
b9 04  <ASCII bytes>  00
```

a two-byte tag, the text, and a NUL terminator. There is no length prefix and no index
table anywhere in the file.

```
862   b9 04 4c 45 56 45 4c 20 20 20 20 20 3a 20 00
      ^^^^^ tag        L  E  V  E  L  _  _  _  _  _  :  _  ^^ terminator
```

Line breaks are their own string: `b9 04 0d 0a 00` is a bare CR LF, which is why the
strings alternate with empty-looking entries.

**Strings are addressed by position.** `b9 04` occurs exactly 99 times in every one of the
four `message*` files and exactly 35 times in both `textin*` files, and the n-th string
means the same thing in each:

| n | `message.io` | `messagee.io` | `messaged.io` | `messagei.io` |
|---|---|---|---|---|
| 4 | `NIVEAU    : ` | `LEVEL     : ` | `LEVEL     : ` | `LIVELLO    : ` |
| 6 | `EXPERIENCE: ` | `EXPERIENCE: ` | `ERFAHRUNG : ` | `ESPERIENZA: ` |
| 20 | `AGILITE      : ` | `AGILITY      : ` | `BEWEGLICHKEIT: ` | `AGILITA'     : ` |

Labels are **padded with spaces to a fixed width** so the colons line up in the character
sheet -- the padding is part of the stored string, not applied at draw time.

### 10.4 Reading them

```
1  decode the container as usual (3.0, 3.2)
2  scan the payload for the two-byte tag b9 04
3  the string runs from tag+2 to the next 00
4  keep them in order; the index is the identity, and it is the same in all four
   language files of a set
```

**Status:** the encoding and the positional correspondence are established. What `b9 04`
*is* as an instruction is not: `0xb9` maps to `seg_0000:2a78`, which sets `ss:[0bac]` to 2
and calls the expression evaluator, so the tag is more likely an opcode plus a one-byte
operand than a two-byte marker. It does not matter for reading the strings out, but a
reader that disassembles rather than scans would need it. See T36.


### 10.5 How much of these files the strings explain: 8-12%

The strings are a small part of a language file. Everything else is script.

| file | decoded | strings | bytes in strings | accounted |
|---|---|---|---|---|
| `message.io` | 8712 | 99 | 1021 | **11%** |
| `messagee.io` | 8416 | 99 | 986 | **11%** |
| `messaged.io` | 8600 | 99 | 1006 | **11%** |
| `messagei.io` | 8600 | 99 | 1027 | **12%** |
| `textin.io` | 11896 | 35 | 1088 | **9%** |
| `textine.io` | 11480 | 35 | 945 | **8%** |

The strings also do not run the length of the file: in `messagee.io` they occupy 679..7027
of 8416 bytes, and in `textine.io` 7649..10375 of 11480 -- the narrative text sits in the
*last* third of its file. Everything before, between and after is unread.

That is enough to translate the game or to build a string table, and nowhere near enough to
reimplement what these files do.

### 10.6 The other 88%: what is known and what is not

A language file is a **script with its strings inline**, and the script is the same in every
language. Splitting `messagee.io` and `message.io` at their string boundaries gives 100
inter-string gaps each, and **79 of the 100 are byte-identical between English and
French** -- so the bulk of the file is language-invariant code.

Of the 21 gaps that do differ, **12 differ only in the operand of a leading `0x0a`**, the
unconditional forward skip (FINDINGS 6.8):

```
gap 14   en  0a b70c 00 bf 00 07 00 0f 02 be 00 00 11
         fr  0a 010d 00 bf 00 07 00 0f 02 be 00 00 11
             ^^ ^^^^ only the skip distance changes
   string 14:  en 'ATTRIBUTES :'   fr 'CARACTERISTIQUES :'

gap 44   en  0a 840a 00 bf 00 07 00 0b 00 37 00 32
         fr  0a cc0a 00 bf 00 07 00 0b 00 37 00 32
   string 44:  en 'GIVE ITEM'      fr 'DONNER OBJET'
```

The displacements are **recomputed per language** because they jump over text that changes
length -- which is what you would expect from a build step that assembles the script with
the translated strings substituted in.

So every byte of a language file falls into one of three buckets:

| bucket | bytes (messagee.io) | share | status |
|---|---|---|---|
| asset header (3.15) | 16 | 0.2% | **decoded** |
| strings, `b9 04 ... 00` (10.3) | 986 | 12% | **decoded** |
| the rest | 7414 | 88% | **not decoded** -- see below for exactly what is and is not known |

#### What "the rest" actually means

It is **not** a decoded region, and calling it "script" is an inference from two
measurements rather than a reading:

1. **It is not text and not language data.** 79 of the 100 gaps are byte-identical between
   English and French.
2. **At least the gap openings are instructions.** 12 of the 21 differing gaps begin with
   `0x0a`, an opcode whose handler is read and understood (`lodsw / inc si / add si,ax`,
   FINDINGS 6.8), and whose operand provably grows with the length of the translated text.

That is the whole basis. **Running `tools/vmdis.py` over this file does not produce a
correct listing**: with no known entry point it mis-aligns and reads the ASCII of
`"LEVEL     : "` as a `vm_op_load_asset` instruction. So the bytes are *consistent with*
bytecode for the VM of section 6, and are not *decoded* bytecode.

Concretely, what a reimplementation gets from this file today: the 99 strings, in order,
matched across four languages. What it does not get: when each is shown, where on screen,
or in response to what -- all of which lives in the 88%.

The 9 differing gaps that the skip-operand explanation does not cover are unexplained
as well.

**Verified by:** the gap-by-gap comparison of `messagee.io` against `message.io` (79 of 100
identical, 12 of the rest differing only in a skip operand); the byte sequences quoted
above.

**Verified by:** counts of the tag across all eight files (99, 99, 99, 99 and 35, 35);
the index-by-index comparison above, which lines up the same label in four languages; and
the asset ids read from each file's own header against the load instructions in `main.io`.

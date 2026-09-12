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

**Looking for one file?** `FILES.md` has every asset's byte map on one page, generated from
the bytes by `tools/anatomy.py --files`. This section explains the structures it names.

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
| 0-2 | `hdr_size` | total size, headers included — **24 bits, little-endian.** 22 is subtracted on the catalogue path (6 + 16), 6 on the direct path |
| 3 | `hdr_mode` | `and 0feh` becomes the decoder's mode at `ss:[0b57]`: `0x80` one pass, `0xa0` two, anything else eight |
| 4-5 | `hdr_is_catalogue` | **the discriminator.** Zero → read the 16-byte directory next; non-zero → decode straight away |

**The size is 24 bits, and reading it as 16 truncated nine assets.** `seg_0000:793a`
loads `ss:[2480]` into CX and `ss:[2482]` into AX; `and ah,0feh` takes the mode out of
AH, and `and ax,0ffh` keeps AL — which is the size's **third byte**. `asset_decode_chunked`
at `seg_0000:79a5` then decodes 64 KB per round, `dec ax` per round, `jnb`/`dec ax`
borrowing across the `sub cx,6`. `and ax,0fh` caps the high byte at 15, so the format's
ceiling is 1 MB.

Nothing else in the game reads `ss:[2482]`'s low byte, so that loop is the whole proof.
`tools/io.py` read the size as a `u16`, and the overflow byte then landed in the *mode*
word's low half where `>>8` discarded it — so the bug was invisible on the 88 assets under
64 KB and silently truncated the nine over it. `dead.io` decoded as 448 bytes of a
65,984-byte asset.

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
- `hdr_size >= file size` in **all 106** once the third byte is read. Under the old
  `u16` reading it held for only 93, and the thirteen exceptions were the tell — a
  compressed file smaller than its own declared output is not a rounding error.
  `blancpc.io` is the one asset seen to load uncompressed, and there the two are equal —
  which is also why it is read whole in a single call instead of in chunks.

**The nine assets over 64 KB**, with their true decoded sizes:

| asset | declared as `u16` | true size | what it turned out to be |
|---|---|---|---|
| `presen.io` | 12,536 | 143,608 | title card; 4 → 7 sprites |
| `theend.io` | 11,816 | 142,888 | layout still unread (3.18) |
| `iboishar.io` | 1,656 | 132,728 | layout still unread (3.18) |
| `ville.io` | 35,176 | 100,712 | town; 33 → 55 sprites |
| `mcave.io` | 21,008 | 86,544 | cave; 4 → **45** sprites |
| `intmais.io` | 14,120 | 79,656 | house interior; 2 → **31** sprites, 89% of the file |
| `stage.io` | 7,432 | 72,968 | 2 sprites, unchanged |
| `dead.io` | 448 | 65,984 | the demon frame (3.18) |
| `auteur.io` | 448 | 65,984 | the credits card (3.18) |

This replaces the earlier guess of "an 11-byte signature at offset 2". There is no
signature: `a1 01 00` is simply the high byte of `hdr_mode` followed by
`hdr_is_catalogue`, and it looks constant because almost every asset shares one mode.

**Verified by:** the annotated disassembly of both header readers (`asset_header_direct`,
`asset_decode_chunked`) and the field values tabulated across every asset file. The width
is independently confirmed from the data: running the LZ bit stream until the reader walks
off the end of the payload gives an output length that the `u24` size predicts for **97 of
97** LZ assets (two land one byte short), and predicted nothing for nine under `u16`.

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

1. **The container header** (3.0). Read as a word, `hdr_mode` is `0xa100` on 88 files,
   `0xa101` on 6 and `0xa102` on 3 — and that low byte is not part of the mode at all, it
   is the **size's third byte**. The six are the assets that decode to 64-128 KB, the three
   to 128-192 KB. This table recorded the overflow before anyone read it as one.
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

**This table predates the 24-bit size fix (3.0) and has not been regenerated.** Two rows
are known wrong: `auteur.io` and `dead.io` are filed as "data" and are whole VGA pages
(3.18), and the sprite counts for `mcave.io`, `intmais.io`, `ville.io` and `presen.io` were
taken from truncated decodes. The current per-asset reading is FINDINGS 4.19, which has
been re-extracted; regenerating `.ish/file-classification.json` is outstanding.

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



#### How much of the assets is actually understood: 43.3%, and the shape matters more

**Updated twice.** `main.io`'s script became readable first (12,399 of its 26,384 bytes,
boundaries confirmed against live execution, 7.2e). Then T37f supplied entry-point sets for
seven more assets, adding **58,453 bytes** of reachable script:

| asset | reachable | of |
|---|---|---|
| `frise.io` | 36,967 | 53,808 |
| `param.io` | 9,872 | 15,680 |
| `geren.io` | 4,603 | 13,088 |
| `samb.io` | 2,390 | 32,880 |
| `dplt.io` | 2,372 | 3,376 |
| `encont.io` | 1,352 | 2,008 |
| `affobj.io` | 897 | 1,432 |

Then a second poll during **varied** gameplay -- menus, the map, portrait clicks, walking,
an attack -- reached assets a quiet walk never touches, taking the set to **15 assets with
entry points** and **124,350 bytes** of readable script outside `main.io`:

| asset | reachable | of | observed PCs covered |
|---|---|---|---|
| `frise.io` | 37,776 | 53,808 | 61/61 |
| `plaine.io` | 20,096 | 32,488 | 26/35 |
| `rplaine.io` | 18,998 | 30,048 | 24/27 |
| `arbre.io` | 17,515 | 25,976 | 26/26 |
| `lacustre.io` | 11,271 | 24,088 | 18/18 |
| `geren.io` | 5,066 | 13,088 | 34/34 |
| `gerdep.io` | 5,011 | 14,472 | 51/51 |
| `samb.io` | 2,393 | 32,880 | 15/15 |
| `dplt.io` | 2,385 | 3,376 | 28/28 |
| `encont.io` | 1,376 | 2,008 | 13/13 |
| `souris.io` | 1,296 | 3,856 | 24/24 |
| `affobj.io` | 913 | 1,432 | 9/9 |

Total: **810,715 of 1,583,646 bytes = 51.2%**, from 42.6% before any script was readable --
past half the corpus. `param.io`, `encont.io` and `affobj.io` were each at 0% beyond their
header when this started.

The remaining shortfalls are visible and fixable rather than mysterious: `plaine.io` covers
26 of 35 observed program counters and `rplaine.io` 24 of 27, so both need more entries,
which means more varied play rather than a new technique.

The percentage moved by less than a point, and that is the honest picture: what changed
this round is not how much is named but how much is *proven*.

| | status |
|---|---|
| container + decompression | **solved, proven twice**: 98/98 files, and a decoder written from this document alone is byte-identical to one written from the disassembly |
| 8bpp pixels | **machine-verified**: `logo.io` 12,850/12,875 opaque pixels identical to VRAM, the 25 differences being a second sprite composited on top |
| 4bpp pixels | **machine-verified**: `buste.io` 1,233/1,233 drawn pixels identical, 0 of 1,071 keyed pixels drawn |
| transparency | **corrected**: five modes, three different rules, read from the dispatcher (3.13c) -- the old "4bpp is opaque" was wrong |
| palettes | group is `word3`'s low byte used directly, confirmed from the code and from a blind reverse search |
| art on disk | 803 sprites extracted as RGBA with real alpha |
| text | strings, the four-language suffix scheme, confirmed live against a running game |
| script | **newly readable**: `main.io` 47%, 231 opcodes tabulated, two entry points known |
| **layout** | **not started** -- every screen position in 4.15 was measured, not derived |

The remaining 56.7% is dominated by script in assets other than `main.io`, and the blocker
there is entry points rather than the encoding: five assets are confirmed running bytecode
and only two have known entries (T37f).

#### The original accounting

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
| `0xCC`, `0xCD` | **water, impassable.** Every refused move in the walk sweep targeted `0xCD` and no accepted move did; rendered, the regions braid like a river system and terminate against the `0xCE` outline (FINDINGS 6.7b). The earlier "MSC uninitialised fill" reading is withdrawn -- `0xCC`/`0xCD` really are that compiler's fill pattern, which is a coincidence, not an explanation |
| `0xE6` | **impassable**, one refusal; one of the large-blob area classes |
| `0x9D` | the interior fill of the built structures -- the walled town in `cont2`, the fortress filling `cont5`. Read off the rendering, not walked |
| `0xDF`-`0xE2` | the enclosure walls of those structures |
| low values (`0x03`-`0x1f` seen) | **walkable**, and numerous -- ~50 values of ~25 cells each in `cont1`. Per-cell scenery markers over a base of `0x00`, not yet tied to sprites |

**Bit 6 is the population split.** Values `0x00`-`0x3F` form components averaging 1.17-1.36
cells -- isolated markers; values `0x40`-`0xFF` average 11-55 -- area terrain. Measured over
`cont1`-`cont5`, the only exceptions are `0x00` itself (the base) and the building-wall
values, which are thin lines because walls are. Branch on `value & 0x40`.

**The tile sets are per region**: only `0x00`, `0x0C`, `0x0F`, `0x10` and `0xCD` occur in all
six grids. `cont1` uses `0x00`-`0x39` and `0xAB`-`0xFF` with nothing between; `cont2` uses
`0x00`-`0x3F`, `0x40`, `0x50` and `0x9D`-`0xE2`. A single global tile table would be wrong.
See FINDINGS 6.7b.
| others | 53-91 distinct values per file: terrain and object types, not yet decoded |

**The six grids are separate regions, not tiles.** No edge of any file continues into any
other except degenerately (`cont5`'s right column and `cont4`'s left are both 54 cells of
`0xCE`; `cont6` is 97% zero). Each is closed by its own `0xCE` outline, so region changes
must be scripted.

**`map.io` is not the same thing.** It decodes normally and autocorrelates at lag 160 --
160 bytes per row is 320 pixels at 4bpp -- so it is the rendered map *picture* shown to
the player, not the grid the game walks on.

**The grid is indexed `row * 90 + col`, and the game keeps it verbatim.** `cont1.fic` is
resident at linear `0x129d0` during play, matching the file across all 4,860 bytes -- so a
rewrite reads `cont*.fic` off disk with no transform.

**It is loaded into the VM's global variable area**, whose base is the far pointer at
`ss:[0bf6]` (`126b:02a0` = `0x12950` in two sessions). Relative to that base:

| global offset | field |
|---|---|
| `+0x0080` | the 90x54 grid, 4,860 bytes |
| `+0x137C` | party row |
| `+0x137D` | party column |
| `+0x3EAC` | region id, 0..20 |

So the world state is one flat byte array the scripts index with `vm_op_load_byte_global`
(expression `0x1e`), and **the only code that reads a map cell is the expression evaluator**
-- there is no native map renderer. See FINDINGS 6.7b and 4.19d.

**Verified by:** autocorrelation over three files independently agreeing on 90; the
rendering itself; the neighbour-count test that isolates `0xCE` as an outline in all
six files; and the walked path, which is inside the map under `row * 90 + col` and outside
it under the transpose.

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

### 6.1b The expression opcode table, all 112 (T46)

Statements are only half the VM. The **expression** table at image `0x01f2` is byte-scaled --
`sub ax,ax / lodsb / mov di,ax / jmp cs:[di+1f2h]` -- so its opcodes are even, and there are
**112** of them across 111 distinct handlers. Until now none of their operands were rendered,
so a script read as a list of statement names with hex after it.

**Fifteen of them are the operator set, consecutive from `0x42` to `0x5e`.** Each calls the
evaluator twice and combines the results, so none carries an inline operand:

| | | | | |
|---|---|---|---|---|
| `0x42` **&** | `0x44` **\|** | `0x46` **^** | `0x48` **^~** (xor then not) | `0x4a` **==** |
| `0x4c` **!=** | `0x4e` **<=** | `0x50` **>=** | `0x52` **<** | `0x54` **>** |
| `0x56` **+** | `0x58` **-** | `0x5a` **/** | `0x5c` **%** | `0x5e` **\*** |

The six comparisons are distinguished by their conditional jump (`jz`, `jnz`, `jle`, `jge`,
`jl`, `jg` in that order), and the two division opcodes differ only in whether they keep the
quotient or the remainder. All fifteen are named in `ishar.chani`.

**The rest load values.** By inline-operand shape: 38 take nothing, 19 a word, 14 a byte, 16
nest another expression, and the remainder take pairs (`wb`, `ww`, `bb`, `wwb`). The named
loaders are `vm_op_load_imm8` (`0x00`), `vm_op_load_imm16` (`0x02`),
`vm_op_load_byte_var_w` (`0x06`), `vm_op_load_word_var_w` (`0x08`), `vm_op_load_far`
(`0x0a`), `vm_op_load_byte_idx_w` (`0x0e`), `vm_op_load_byte_var_b` (`0x12`) and
`vm_op_load_word_var_b` (`0x14`).

`tools/vmi.py --listing` now renders expressions infix, so a statement reads as
`vm_stmt_eval e38[wordvar[48]]` rather than as raw bytes.

| opcode | handler | name | inline operands | nests | operator |
|---|---|---|---|---|---|
| `0x00` | `seg_0000:69c7` | vm_op_load_imm8 | b | — |  |
| `0x02` | `seg_0000:69cc` | vm_op_load_imm16 | w | — |  |
| `0x04` | `seg_0000:69d0` | — | b | — |  |
| `0x06` | `seg_0000:69e3` | vm_op_load_byte_var_w | w | — |  |
| `0x08` | `seg_0000:69ed` | vm_op_load_word_var_w | w | — |  |
| `0x0a` | `seg_0000:69f4` | vm_op_load_far | wb | — |  |
| `0x0c` | `seg_0000:6a2d` | — | wb | — |  |
| `0x0e` | `seg_0000:6a16` | vm_op_load_byte_idx_w | w | — |  |
| `0x10` | `seg_0000:6a23` | — | w | — |  |
| `0x12` | `seg_0000:6a52` | vm_op_load_byte_var_b | b | — |  |
| `0x14` | `seg_0000:6a5e` | vm_op_load_word_var_b | b | — |  |
| `0x16` | `seg_0000:6a67` | — | bb | — |  |
| `0x18` | `seg_0000:6aa6` | — | bb | — |  |
| `0x1a` | `seg_0000:6a8b` | vm_op_load_byte_idx_b | b | — |  |
| `0x1c` | `seg_0000:6a9a` | vm_op_load_word_idx_b | b | — |  |
| `0x1e` | `seg_0000:6acd` | vm_op_load_byte_global | w | — |  |
| `0x20` | `seg_0000:6adc` | — | w | — |  |
| `0x22` | `seg_0000:6ae8` | — | wb | — |  |
| `0x24` | `seg_0000:6b32` | — | wb | — |  |
| `0x26` | `seg_0000:6b0b` | — | w | — |  |
| `0x28` | `seg_0000:6b20` | — | w | — |  |
| `0x2a` | `seg_0000:6b5c` | — | ww | — |  |
| `0x2c` | `seg_0000:6b74` | — | ww | — |  |
| `0x2e` | `seg_0000:6b89` | — | wwb | — |  |
| `0x30` | `seg_0000:6bf6` | — | wwb | — |  |
| `0x32` | `seg_0000:6bb7` | — | ww | — |  |
| `0x34` | `seg_0000:6bd8` | — | ww | — |  |
| `0x36` | `seg_0000:7147` | — | — | — |  |
| `0x38` | `seg_0000:7150` | — | — | yes |  |
| `0x3a` | `seg_0000:7156` | — | — | — |  |
| `0x40` | `seg_0000:7140` | — | — | — |  |
| `0x42` | `seg_0000:6cc5` | expr_and | — | yes | **&** |
| `0x44` | `seg_0000:6ccb` | expr_or | — | yes | **|** |
| `0x46` | `seg_0000:6cd1` | expr_xor | — | yes | **^** |
| `0x48` | `seg_0000:6cd7` | expr_xnor | — | yes | **^~** |
| `0x4a` | `seg_0000:6cdf` | expr_eq | — | yes | **==** |
| `0x4c` | `seg_0000:6ced` | expr_ne | — | yes | **!=** |
| `0x4e` | `seg_0000:6cfb` | expr_le | — | yes | **<=** |
| `0x50` | `seg_0000:6d09` | expr_ge | — | yes | **>=** |
| `0x52` | `seg_0000:6d17` | expr_lt | — | yes | **<** |
| `0x54` | `seg_0000:6d25` | expr_gt | — | yes | **>** |
| `0x56` | `seg_0000:6d33` | expr_add | — | yes | **+** |
| `0x58` | `seg_0000:6d39` | expr_sub | — | yes | **-** |
| `0x5a` | `seg_0000:6d41` | expr_div | — | yes | **/** |
| `0x5c` | `seg_0000:6d53` | expr_mod | — | yes | **%** |
| `0x5e` | `seg_0000:6d67` | expr_mul | — | yes | ***** |
| `0x60` | `seg_0000:6d71` | — | — | — |  |
| `0x62` | `seg_0000:6d74` | — | — | — |  |
| `0x64` | `seg_0000:6d7b` | — | — | — |  |
| `0x66` | `seg_0000:6d94` | — | — | — |  |
| `0x68` | `seg_0000:6da2` | — | — | — |  |
| `0x6a` | `seg_0000:6db4` | — | — | — |  |
| `0x6c` | `seg_0000:6dc7` | — | — | — |  |
| `0x6e` | `seg_0000:6dd6` | — | — | — |  |
| `0x70` | `seg_0000:6de2` | — | — | — |  |
| `0x72` | `seg_0000:5854` | — | — | — |  |
| `0x74` | `seg_0000:6dc8` | — | — | — |  |
| `0x76` | `seg_0000:6df4` | — | — | — |  |
| `0x78` | `seg_0000:6df8` | — | — | — |  |
| `0x7a` | `seg_0000:6dd0` | — | — | — |  |
| `0x7c` | `seg_0000:6dfe` | — | — | — |  |
| `0x7e` | `seg_0000:6e13` | — | bb | — |  |
| `0x80` | `seg_0000:6e4f` | — | b | — |  |
| `0x82` | `seg_0000:6e83` | — | b | — |  |
| `0x84` | `seg_0000:6f2b` | — | — | — |  |
| `0x86` | `seg_0000:6f38` | — | — | — |  |
| `0x88` | `seg_0000:7108` | — | b | — |  |
| `0x8a` | `seg_0000:70ae` | — | — | — |  |
| `0x8c` | `seg_0000:70bd` | — | — | — |  |
| `0x8e` | `seg_0000:70cc` | — | — | — |  |
| `0x90` | `seg_0000:70db` | — | — | — |  |
| `0x92` | `seg_0000:70ea` | — | — | — |  |
| `0x94` | `seg_0000:70f9` | — | — | — |  |
| `0x96` | `seg_0000:7093` | — | — | — |  |
| `0x98` | `seg_0000:7097` | — | — | — |  |
| `0x9a` | `seg_0000:6e9e` | — | — | — |  |
| `0x9c` | `seg_0000:6f55` | — | — | — |  |
| `0x9e` | `seg_0000:6f45` | — | — | — |  |
| `0xa0` | `seg_0000:6f6d` | — | — | — |  |
| `0xa2` | `seg_0000:6fde` | — | — | — |  |
| `0xa4` | `seg_0000:6fe6` | — | — | — |  |
| `0xa6` | `seg_0000:6dde` | — | — | — |  |
| `0xa8` | `seg_0000:6fec` | — | — | — |  |
| `0xb0` | `seg_0000:715a` | — | w | — |  |
| `0xb2` | `seg_0000:7161` | — | w | — |  |
| `0xb4` | `seg_0000:7168` | — | wb | — |  |
| `0xb6` | `seg_0000:71a3` | — | wb | — |  |
| `0xb8` | `seg_0000:7183` | — | w | — |  |
| `0xba` | `seg_0000:7193` | — | w | — |  |
| `0xbc` | `seg_0000:71c1` | — | b | — |  |
| `0xbe` | `seg_0000:71ca` | — | b | — |  |
| `0xc0` | `seg_0000:71d3` | — | bb | — |  |
| `0xc2` | `seg_0000:7214` | — | bb | — |  |
| `0xc4` | `seg_0000:71f0` | — | b | — |  |
| `0xc6` | `seg_0000:7202` | — | b | — |  |
| `0xc8` | `seg_0000:7234` | — | w | — |  |
| `0xca` | `seg_0000:7240` | — | w | — |  |
| `0xcc` | `seg_0000:724c` | — | wb | — |  |
| `0xce` | `seg_0000:729c` | — | wb | — |  |
| `0xd0` | `seg_0000:726c` | — | w | — |  |
| `0xd2` | `seg_0000:7284` | — | w | — |  |
| `0xd4` | `seg_0000:72c5` | — | ww | — |  |
| `0xd6` | `seg_0000:72da` | — | ww | — |  |
| `0xd8` | `seg_0000:72ef` | — | wwb | — |  |
| `0xda` | `seg_0000:7360` | — | wwb | — |  |
| `0xdc` | `seg_0000:7318` | — | ww | — |  |
| `0xde` | `seg_0000:733c` | — | ww | — |  |
| `0xe0` | `seg_0000:7393` | — | — | — |  |
| `0xe2` | `seg_0000:739a` | — | b | — |  |
| `0xe4` | `seg_0000:7156` | — | — | — |  |
| `0xec` | `seg_0000:73b0` | — | w | — |  |
| `0xee` | `seg_0000:73b7` | — | w | — |  |

**Verified by:** the table read from the image; each handler walked from `ishar-listing.txt`
to its `ret`; the operators classified by the arithmetic instruction they apply and the
comparisons by their conditional jump.

### 7.2b The statement opcode table, all 231 (T39b)

Opcode facts had been spread across `ishar.chani` (named handlers), section 6 (the four
tables), FINDINGS 6.3 (signatures) and `tools/vmi.py` (sizing), with no one place to look
one up. This is that place. Every row is **derived from the handler's own instructions**
by `tools/vmi.py`, not hand-entered; regenerate it rather than editing it.

Columns: **operands** are the fixed `lodsb`/`lodsw` reads (`b` = byte, `w` = word);
**embeds expr** means the handler calls the expression evaluator, so a nested expression
from the byte-scaled table at `0x01f2` sits between the opcode and its own operands and
the statement's length is not fixed (7.3); **control flow** gives the branch shape, where
`base` is the offset from the opcode at which the displacement is applied.

Totals: **85** opcodes take nothing and do nothing to the stream (many are bare `ret`
no-ops), **105** embed an expression, **22** are branch-shaped, **2** are variable-length
(`0x29`, `0x46` — see 7.4), and **165** are named in `ishar.chani`.

The five shapes checked by hand against live execution all match what the derivation
produces: `0x0a` jump d16 base +4, `0x08` jump d8 base +2, `0x14` and `0x1a` conditional
d16 base +4, `0x06` call d16 base +3.

| opcode | handler | name | operands | embeds expr | control flow |
|---|---|---|---|---|---|
| `0x00` | `seg_0000:26f9` | vm_stmt_00 | — | — | — |
| `0x01` | `seg_0000:26fa` | vm_stmt_01 | — | — | — |
| `0x02` | `seg_0000:26fb` | vm_stmt_02 | — | — | — |
| `0x03` | `seg_0000:26fc` | vm_stmt_03 | — | — | — |
| `0x04` | `seg_0000:0022` | — | — | — | — |
| `0x05` | `seg_0000:26fe` | — | b | — | call d8, base +2 |
| `0x06` | `seg_0000:2711` | vm_op_call_word | w | — | call d16, base +3 |
| `0x07` | `seg_0000:2723` | — | w | — | call d16, base +4 |
| `0x08` | `seg_0000:2736` | vm_op_jump_byte | b | — | jump d8, base +2 |
| `0x09` | `seg_0000:273b` | vm_stmt_09 | w | — | jump d16, base +3 |
| `0x0a` | `seg_0000:273f` | vm_op_jump_word | w | — | jump d16, base +4 |
| `0x0b` | `seg_0000:2802` | vm_stmt_0b | — | — | — |
| `0x0c` | `seg_0000:2803` | vm_stmt_0c | — | — | — |
| `0x0d` | `seg_0000:2804` | vm_stmt_0d | — | — | — |
| `0x0e` | `seg_0000:2805` | vm_stmt_0e | — | — | — |
| `0x0f` | `seg_0000:2806` | vm_stmt_0f | — | — | — |
| `0x10` | `seg_0000:2807` | vm_stmt_10 | — | — | — |
| `0x11` | `seg_0000:2808` | — | — | — | — |
| `0x12` | `seg_0000:2885` | — | b | — | cond d8, base +2 |
| `0x13` | `seg_0000:2890` | — | w | — | cond d16, base +3 |
| `0x14` | `seg_0000:289c` | vm_op_jump_if_zero | w | — | cond d16, base +4 |
| `0x15` | `seg_0000:28a9` | — | b | — | cond d8, base +2 |
| `0x16` | `seg_0000:28b4` | — | w | — | cond d16, base +3 |
| `0x17` | `seg_0000:28c0` | vm_stmt_17 | w | — | cond d16, base +4 |
| `0x18` | `seg_0000:28cd` | vm_stmt_18 | b | — | cond d8, base +2 |
| `0x19` | `seg_0000:28d8` | vm_stmt_19 | w | — | cond d16, base +3 |
| `0x1a` | `seg_0000:28e4` | vm_stmt_1a | w | — | cond d16, base +4 |
| `0x1b` | `seg_0000:28f1` | vm_stmt_1b | b | — | cond d8, base +2 |
| `0x1c` | `seg_0000:28fc` | vm_stmt_1c | w | — | cond d16, base +3 |
| `0x1d` | `seg_0000:2908` | vm_stmt_1d | w | — | cond d16, base +4 |
| `0x1e` | `seg_0000:2915` | vm_op_eval_reset | b | yes | — |
| `0x1f` | `seg_0000:2937` | vm_stmt_eval | — | yes | — |
| `0x20` | `seg_0000:293d` | vm_stmt_assign | b | yes | — |
| `0x21` | `seg_0000:295f` | vm_stmt_assign_neg | — | yes | — |
| `0x22` | `seg_0000:2969` | vm_stmt_22 | — | — | — |
| `0x23` | `seg_0000:296a` | vm_stmt_23 | — | — | — |
| `0x24` | `seg_0000:2a92` | — | — | yes | — |
| `0x25` | `seg_0000:2a9f` | vm_stmt_25 | b | — | — |
| `0x26` | `seg_0000:2ab1` | vm_stmt_26 | — | yes | — |
| `0x27` | `seg_0000:2ace` | vm_stmt_27 | — | yes | — |
| `0x28` | `seg_0000:2ae2` | vm_stmt_28 | — | yes | — |
| `0x29` | `seg_0000:5713` | — | wbbw | — | **variable length** |
| `0x2a` | `seg_0000:2afc` | vm_op_wait_tick | — | yes | — |
| `0x2b` | `seg_0000:2837` | vm_op_loop | — | — | — |
| `0x2c` | `seg_0000:2850` | vm_stmt_2c | — | — | — |
| `0x2d` | `seg_0000:286a` | vm_stmt_2d | — | — | — |
| `0x2e` | `seg_0000:5738` | — | b | yes | cond d8, base +3 |
| `0x2f` | `seg_0000:5768` | — | b | yes | cond d8, base +3 |
| `0x30` | `seg_0000:2744` | vm_op_jump_rel8 | b | — | — |
| `0x31` | `seg_0000:2749` | vm_stmt_31 | w | — | — |
| `0x32` | `seg_0000:27b9` | vm_op_jump_rel16 | w | — | — |
| `0x33` | `seg_0000:27bd` | vm_stmt_33 | — | — | — |
| `0x34` | `seg_0000:67b5` | vm_prim_1arg | — | yes | — |
| `0x35` | `seg_0000:5798` | vm_stmt_35 | — | yes | — |
| `0x36` | `seg_0000:26f9` | vm_stmt_00 | — | — | — |
| `0x37` | `seg_0000:26f9` | vm_stmt_00 | — | — | — |
| `0x38` | `seg_0000:2e9b` | vm_stmt_38 | — | yes | — |
| `0x39` | `seg_0000:2ec0` | vm_stmt_39 | — | yes | — |
| `0x3a` | `seg_0000:2e94` | vm_stmt_3a | — | — | — |
| `0x3b` | `seg_0000:2e93` | — | — | — | — |
| `0x3c` | `seg_0000:2cce` | vm_stmt_3c | — | — | — |
| `0x3d` | `seg_0000:2de5` | — | w | — | — |
| `0x3e` | `seg_0000:57c1` | — | — | yes | — |
| `0x3f` | `seg_0000:57b0` | — | — | — | — |
| `0x40` | `seg_0000:2ce2` | — | w | — | — |
| `0x41` | `seg_0000:2d80` | — | — | yes | — |
| `0x42` | `seg_0000:2d94` | — | — | — | — |
| `0x43` | `seg_0000:2d98` | vm_stmt_43 | — | — | — |
| `0x44` | `seg_0000:2da7` | — | — | — | — |
| `0x45` | `seg_0000:2dbd` | vm_op_load_asset | wb | — | — |
| `0x46` | `seg_0000:2ded` | — | wb | — | **variable length** |
| `0x47` | `seg_0000:2ef3` | — | w | — | — |
| `0x48` | `seg_0000:333f` | — | — | yes | — |
| `0x49` | `seg_0000:336f` | — | — | yes | — |
| `0x4a` | `seg_0000:3aae` | vm_stmt_4a | — | — | — |
| `0x4b` | `seg_0000:3a84` | vm_op_draw_menu | — | yes | — |
| `0x4c` | `seg_0000:3b86` | — | — | yes | — |
| `0x4d` | `seg_0000:3b9c` | vm_stmt_4d | — | yes | — |
| `0x4e` | `seg_0000:325f` | — | w | — | — |
| `0x4f` | `seg_0000:3279` | — | w | — | — |
| `0x50` | `seg_0000:3adb` | — | — | — | — |
| `0x51` | `seg_0000:48b5` | — | — | yes | — |
| `0x52` | `seg_0000:48bd` | vm_stmt_52 | — | — | — |
| `0x53` | `seg_0000:4a15` | vm_stmt_53 | — | yes | — |
| `0x54` | `seg_0000:4ae1` | vm_stmt_54 | — | yes | — |
| `0x55` | `seg_0000:4b17` | vm_stmt_55 | — | yes | — |
| `0x56` | `seg_0000:4b59` | vm_stmt_56 | — | yes | — |
| `0x57` | `seg_0000:4b8f` | — | — | — | — |
| `0x58` | `seg_0000:4ba4` | vm_stmt_58 | — | — | — |
| `0x59` | `seg_0000:551a` | — | — | — | — |
| `0x5a` | `seg_0000:5353` | vm_stmt_5a | w | yes | — |
| `0x5b` | `seg_0000:5274` | vm_stmt_5b | — | yes | — |
| `0x5c` | `seg_0000:55dc` | vm_stmt_5c | — | yes | — |
| `0x5d` | `seg_0000:5594` | vm_stmt_5d | w | yes | — |
| `0x5e` | `seg_0000:556b` | vm_stmt_5e | — | yes | — |
| `0x5f` | `seg_0000:3c3b` | vm_stmt_5f | — | yes | — |
| `0x60` | `seg_0000:4bc4` | vm_stmt_60 | — | — | — |
| `0x61` | `seg_0000:57d9` | — | b | yes | — |
| `0x62` | `seg_0000:58a1` | — | — | — | — |
| `0x63` | `seg_0000:5898` | vm_stmt_63 | — | — | — |
| `0x64` | `seg_0000:58ad` | — | — | — | — |
| `0x65` | `seg_0000:58a7` | vm_stmt_65 | — | — | — |
| `0x66` | `seg_0000:588a` | — | — | — | — |
| `0x67` | `seg_0000:570b` | — | — | — | — |
| `0x68` | `seg_0000:591e` | — | — | yes | — |
| `0x69` | `seg_0000:5b6c` | vm_stmt_69 | — | yes | — |
| `0x6a` | `seg_0000:58b3` | — | — | yes | — |
| `0x6b` | `seg_0000:5db8` | vm_stmt_6b | — | yes | — |
| `0x6c` | `seg_0000:5dff` | vm_stmt_6c | — | yes | — |
| `0x6d` | `seg_0000:5ea7` | — | — | yes | — |
| `0x6e` | `seg_0000:60d0` | vm_stmt_6e | — | yes | — |
| `0x6f` | `seg_0000:58bc` | vm_stmt_6f | ww | — | — |
| `0x70` | `seg_0000:637f` | — | bw | yes | cond d8, base +2 |
| `0x71` | `seg_0000:63a8` | — | — | — | — |
| `0x72` | `seg_0000:63ab` | vm_stmt_72 | bw | — | — |
| `0x73` | `seg_0000:63ba` | vm_stmt_73 | b | — | — |
| `0x74` | `seg_0000:63c5` | vm_stmt_74 | — | — | — |
| `0x75` | `seg_0000:63de` | vm_stmt_75 | — | yes | — |
| `0x76` | `seg_0000:63f8` | vm_stmt_76 | b | — | — |
| `0x77` | `seg_0000:6408` | — | wwww | — | — |
| `0x78` | `seg_0000:643c` | vm_stmt_78 | wwwww | — | — |
| `0x79` | `seg_0000:649a` | vm_stmt_79 | — | yes | — |
| `0x7a` | `seg_0000:64c2` | vm_stmt_7a | — | yes | — |
| `0x7b` | `seg_0000:64c9` | vm_stmt_7b | — | yes | — |
| `0x7c` | `seg_0000:64d0` | vm_stmt_7c | — | yes | — |
| `0x7d` | `seg_0000:65c6` | vm_stmt_7d | — | yes | — |
| `0x7e` | `seg_0000:65d8` | vm_stmt_7e | — | yes | — |
| `0x7f` | `seg_0000:65e9` | vm_stmt_7f | — | yes | — |
| `0x80` | `seg_0000:65fa` | vm_stmt_80 | — | yes | — |
| `0x81` | `seg_0000:6603` | vm_stmt_81 | — | yes | — |
| `0x82` | `seg_0000:67ae` | vm_stmt_82 | — | yes | — |
| `0x83` | `seg_0000:3678` | — | — | yes | — |
| `0x84` | `seg_0000:660d` | — | — | — | — |
| `0x85` | `seg_0000:662e` | vm_stmt_85 | — | — | — |
| `0x86` | `seg_0000:6649` | vm_stmt_86 | — | — | — |
| `0x87` | `seg_0000:665c` | — | — | yes | — |
| `0x88` | `seg_0000:675d` | vm_stmt_88 | — | yes | — |
| `0x89` | `seg_0000:6789` | vm_stmt_89 | b | — | jump d8, base +2 |
| `0x8a` | `seg_0000:6797` | vm_stmt_8a | w | — | — |
| `0x8b` | `seg_0000:26f9` | vm_stmt_00 | — | — | — |
| `0x8c` | `seg_0000:68b6` | — | — | — | — |
| `0x8d` | `seg_0000:692a` | vm_stmt_8d | — | yes | — |
| `0x8e` | `seg_0000:4a57` | vm_stmt_8e | — | yes | — |
| `0x8f` | `seg_0000:4a9c` | vm_stmt_8f | — | yes | — |
| `0x90` | `seg_0000:3bb2` | vm_stmt_90 | — | — | — |
| `0x91` | `seg_0000:679d` | vm_stmt_91 | w | — | — |
| `0x92` | `seg_0000:67a8` | vm_stmt_92 | w | — | — |
| `0x93` | `seg_0000:50bd` | vm_stmt_93 | — | yes | — |
| `0x94` | `seg_0000:510f` | — | w | — | — |
| `0x95` | `seg_0000:6219` | — | — | yes | — |
| `0x96` | `seg_0000:629b` | — | — | yes | — |
| `0x97` | `seg_0000:60eb` | vm_stmt_97 | — | yes | — |
| `0x98` | `seg_0000:60dd` | vm_stmt_98 | — | yes | — |
| `0x99` | `seg_0000:3339` | vm_stmt_99 | — | — | — |
| `0x9a` | `seg_0000:332d` | vm_stmt_9a | — | — | — |
| `0x9b` | `seg_0000:3333` | vm_stmt_9b | — | — | — |
| `0x9c` | `seg_0000:51af` | — | — | — | — |
| `0x9d` | `seg_0000:62bb` | — | — | yes | — |
| `0x9e` | `seg_0000:6370` | vm_stmt_9e | — | — | — |
| `0x9f` | `seg_0000:368f` | vm_stmt_9f | — | — | — |
| `0xa0` | `seg_0000:3695` | — | — | — | — |
| `0xa1` | `seg_0000:6379` | — | — | — | — |
| `0xa2` | `seg_0000:3bce` | vm_stmt_a2 | — | — | — |
| `0xa3` | `seg_0000:4967` | vm_stmt_a3 | — | yes | — |
| `0xa4` | `seg_0000:49a2` | vm_stmt_a4 | — | yes | — |
| `0xa5` | `seg_0000:49dd` | vm_stmt_a5 | — | yes | — |
| `0xa6` | `seg_0000:33a3` | vm_stmt_a6 | — | — | — |
| `0xa7` | `seg_0000:33b7` | — | — | — | — |
| `0xa8` | `seg_0000:33cb` | vm_stmt_a8 | — | — | — |
| `0xa9` | `seg_0000:33dc` | vm_stmt_a9 | — | — | — |
| `0xaa` | `seg_0000:3401` | vm_stmt_aa | — | — | — |
| `0xab` | `seg_0000:33ec` | vm_stmt_ab | — | — | — |
| `0xac` | `seg_0000:6210` | vm_stmt_ac | — | — | — |
| `0xad` | `seg_0000:48c4` | vm_stmt_ad | — | yes | — |
| `0xae` | `seg_0000:2ca5` | vm_stmt_ae | — | yes | — |
| `0xaf` | `seg_0000:2cbc` | vm_stmt_af | — | — | — |
| `0xb0` | `seg_0000:29c4` | vm_stmt_b0 | — | — | — |
| `0xb1` | `seg_0000:29b5` | vm_stmt_b1 | — | — | — |
| `0xb2` | `seg_0000:26f9` | vm_stmt_00 | — | — | — |
| `0xb3` | `seg_0000:26f9` | vm_stmt_00 | — | — | — |
| `0xb4` | `seg_0000:26f9` | vm_stmt_00 | — | — | — |
| `0xb5` | `seg_0000:26f9` | vm_stmt_00 | — | — | — |
| `0xb6` | `seg_0000:2a6b` | vm_stmt_b6 | — | yes | — |
| `0xb7` | `seg_0000:2a5e` | vm_stmt_b7 | — | — | — |
| `0xb8` | `seg_0000:2a85` | vm_stmt_b8 | — | yes | — |
| `0xb9` | `seg_0000:2a78` | — | — | — | — |
| `0xba` | `seg_0000:296b` | vm_prim_5args | — | yes | — |
| `0xbb` | `seg_0000:65cf` | vm_stmt_bb | — | yes | — |
| `0xbc` | `seg_0000:5c08` | — | — | — | — |
| `0xbd` | `seg_0000:5b8b` | vm_stmt_bd | — | yes | — |
| `0xbe` | `seg_0000:5b92` | — | — | yes | — |
| `0xbf` | `seg_0000:2994` | vm_prim_4args | — | yes | — |
| `0xc0` | `seg_0000:2eff` | vm_stmt_c0 | — | yes | — |
| `0xc1` | `seg_0000:2f41` | vm_stmt_c1 | — | yes | — |
| `0xc2` | `seg_0000:2f21` | vm_stmt_c2 | — | yes | — |
| `0xc3` | `seg_0000:2f61` | vm_stmt_c3 | — | yes | — |
| `0xc4` | `seg_0000:2f8f` | vm_stmt_c4 | — | yes | — |
| `0xc5` | `seg_0000:3025` | vm_stmt_c5 | — | yes | — |
| `0xc6` | `seg_0000:3052` | vm_stmt_c6 | — | yes | — |
| `0xc7` | `seg_0000:3680` | vm_stmt_c7 | — | yes | — |
| `0xc8` | `seg_0000:31eb` | vm_stmt_c8 | — | — | — |
| `0xc9` | `seg_0000:31ec` | vm_stmt_c9 | — | — | — |
| `0xca` | `seg_0000:515f` | vm_stmt_ca | — | yes | — |
| `0xcb` | `seg_0000:543b` | vm_stmt_cb | w | yes | — |
| `0xcc` | `seg_0000:55b8` | vm_stmt_cc | w | yes | — |
| `0xcd` | `seg_0000:61a1` | — | — | yes | — |
| `0xce` | `seg_0000:6198` | vm_stmt_ce | — | — | — |
| `0xcf` | `seg_0000:36c8` | — | — | yes | — |
| `0xd0` | `seg_0000:369b` | vm_stmt_d0 | — | yes | — |
| `0xd1` | `seg_0000:5d1c` | vm_stmt_d1 | — | yes | — |
| `0xd2` | `seg_0000:5d75` | vm_stmt_d2 | — | yes | — |
| `0xd3` | `seg_0000:5f00` | vm_stmt_d3 | — | — | — |
| `0xd4` | `seg_0000:6da5` | vm_stmt_d4 | — | — | — |
| `0xd5` | `seg_0000:62b7` | — | — | yes | — |
| `0xd6` | `seg_0000:36d0` | vm_stmt_d6 | — | yes | — |
| `0xd7` | `seg_0000:58d5` | — | — | yes | — |
| `0xd8` | `seg_0000:58ce` | — | — | yes | — |
| `0xd9` | `seg_0000:6da6` | vm_stmt_d9 | — | yes | — |
| `0xda` | `seg_0000:6daa` | vm_stmt_da | — | — | — |
| `0xdb` | `seg_0000:3aa4` | vm_stmt_db | — | — | — |
| `0xdc` | `seg_0000:3ad1` | — | — | — | — |
| `0xdd` | `seg_0000:3a7a` | — | — | — | — |
| `0xde` | `seg_0000:2d76` | — | — | — | — |
| `0xdf` | `seg_0000:3225` | vm_stmt_df | — | yes | — |
| `0xe0` | `seg_0000:31ed` | vm_stmt_e0 | — | yes | — |
| `0xe1` | `seg_0000:4bcd` | vm_stmt_e1 | — | — | — |
| `0xe2` | `seg_0000:7d4e` | — | — | yes | — |
| `0xe3` | `seg_0000:306e` | vm_stmt_e3 | ww | yes | — |
| `0xe4` | `seg_0000:30e5` | vm_stmt_e4 | ww | yes | — |
| `0xe5` | `seg_0000:3142` | vm_stmt_e5 | ww | yes | — |
| `0xe6` | `seg_0000:58e5` | vm_stmt_e6 | — | yes | — |

**Verified by:** `tools/vmi.py`'s `walk()`, reading each handler from `ishar-listing.txt`
and stopping at its `ret` or the next handler start; the five hand-checked shapes above;
and recursive traversal from `main.io`'s entry reaching 4,811 statements with **no stall
on any in-range opcode**.

### 7.2c Two statements end `vm_run`, and an unresolved puzzle about yields (T39b)

`vm_run` is a loop -- fetch, `call cs:[bx+24h]`, jump back -- so a handler can only leave
it by discarding `vm_run`'s own return address. Exactly two do:

| opcode | handler | code |
|---|---|---|
| `0x42` | `seg_0000:2d94` | `add sp,2 / ret` |
| `0x43` | `seg_0000:2d98` | `cmp ss:[0c19],0 / jz 2d94 / call 2808 / add sp,2` |

`0x42` is the **second most common opcode in `main.io`** (930 uses), so this is the normal
way a script gives control back. It is a *yield*, not a stop: the caller immediately does
`mov es:[bp-8], si` (7.5), so the script resumes at the following statement.

**A test that should have confirmed that, and does not.** If a yield saves SI just past
the opcode, then every offset caught by a `MEMORY_WRITE` on the PC slot should sit exactly
one byte after a `0x42` or `0x43`. None of the four observed does:

| asset | first yield | preceding byte |
|---|---|---|
| `main.io` | 256 | `0x29` |
| `logo.io` | 256 | `0x14` |
| `blancpc.io` | 801 | `0x12` |
| `fbuis.io` | 3960 | `0x00` |

So either those offsets are not yields of this kind, or the base used to turn a live
`DS:SI` into an asset offset is wrong. Unresolved, and recorded here so the idea is not
retried blind.

Treating the two as terminal in traversal was also tried and is wrong: coverage falls
**42.8% -> 8.7%**, which is the strongest evidence that control really does continue past
them.

### 7.2d Traversal: validate a target before following it (T39b)

Recursive traversal of `main.io` stalled 56 times on bytes with no opcode entry. Tracing
each stall back to the branch that first entered the data showed **56 different branches**,
across opcodes including four checked by hand -- so it was not one wrong shape. Following a
single bad target puts the walk inside a data block where every later step is garbage, and
each stall was just where that particular wander stopped.

The fix is to check a target before taking it: there are exactly **231** statement opcodes,
so a computed target landing on a byte outside the table cannot be code.

| | before | after |
|---|---|---|
| stalls on non-opcodes | 56 | **0** |
| statements reached | 4,811 | 4,755 |
| byte coverage | 42.8% | 42.6% |
| targets rejected | — | 116 |

Coverage barely moves, which is the point: the extra 56 statements had been fictional.

**The rejections are not a base error.** For the two worst offenders the current shape is
already the best available -- `0x06` base 3 gives 61/87 plausible targets against 60, 60,
61, 60 for bases 1-5, and `0x0a` base 4 gives 121/141 against 118-119 either side. Both
match the shapes verified by hand against live execution.

Note also that "lands on a valid opcode" is a *weak* test here: 231 of 256 byte values are
valid, so ~90% of random targets pass it. `0x06` managing only 70% says those sites are
being decoded at PCs that are themselves wrong.

**The acceptance number that matters is live coverage.** Against 34 IP-verified `DS:SI`
values sampled at `vm_run` during gameplay, traversal from the entry hits **25 of 34 =
73.5%** of the statements the VM actually executed. That is a far better measure than byte
coverage, and it is the one to move.

The nine misses cluster at 19919-20130 and are all opcodes `0x1f` and `0x14`. One of them,
19919, is the fall-through of the unconditional jump at 19915 (`0a de 00`, target 20141) --
so it is not reached by that path at all and must have an **incoming edge from somewhere
traversal does not compute**. The remaining gap is missing in-edges, not wrong lengths.

**Verified by:** the before/after table above; the base sweep; and the live comparison
against `.ish/live-offsets.json`, sampled with `r["ip"] == entry` checked at every stop.

### 7.2e `main.io` has two entry points, and traversal then covers 100% of live execution (T39d)

The nine statements the VM executed that traversal from offset 24 never reached are not a
sizing problem. Searching the **whole file** for any static displacement that lands on
them:

- **five have zero candidate in-edges anywhere in `main.io`** (19919, 19929, 20071, 20100,
  20104);
- the other four are reachable only *from those five* (19929 -> 20064, 20071 -> 20091,
  20100 -> 20130, 20125 -> 20130).

So the region is a closed subgraph with no way in from the rest of the script. It is not
called; it is **entered by the engine**, exactly as 7.5's `es:[bp-8]` model allows.

Adding **19919** as a second entry:

| entries | statements | bytes | live coverage |
|---|---|---|---|
| 24 | 4,755 | 42.6% | 25/34 = 73.5% |
| 24 + 19919 | 5,433 | 47.0% | **34/34 = 100.0%** |

Every statement observed executing is now reached statically, with no stalls. `19919` is
the better root than `19929`: from it the region covers all nine misses, from `19929` only
eight.

**So a script has more than one entry point**, and the loader entry (24) is only the first.
That is what T37e should be looking for in other assets -- not one offset per asset.

### 7.2g Statement `0x2f` is a jump-table switch

The first multi-way branch found in this VM, and the reason a script can pick one of
twenty-one strings without twenty-one tests. Handler `vm_op_switch` at `seg_0000:5768`:

```
2f  <expression>  <count:u8>  [pad so SI is even]  <bias:i16>  <count+1 x i16>
```

| step | instructions |
|---|---|
| selector | `call 069a6` -- the expression evaluator, result in DX |
| count | `lodsb / sub ah,ah / mov cx,ax` |
| align | `test si,1 / jz / inc si` -- the table is word-aligned |
| bias | `add dx,[si]` -- so cases need not start at zero |
| range | `js default` and `cmp dx,cx / ja default` |
| dispatch | `add si,2 / shl dx,1 / add si,dx / add si,[si] / add si,2` |
| default | `add si,4 / shl cx,1 / add si,cx` -- steps over the whole table |

Note the displacement is relative to its **own slot**, not to the table's start, and the
bias is a *signed* word added before the range check, so `js` catches selectors below the
first case.

**Worked example, the region caption** (FINDINGS 4.19b). `gerdep.io` offset 8829:

```
2f  1e ac 3e  14  01 00  7e 01  2a 00  39 00  48 00 ... 47 01
^   ^         ^   ^      ^----- 21 signed displacements, 0x0f apart after the first
|   |         |   bias = 1
|   |         count = 0x14, so cases 0..20
|   vm_op_load_byte_global 0x3eac -- the region id
switch
```

Each arm is a 17-byte statement that prints one region name. This is what made the id
findable: the operand of the selector expression names the variable outright.

**Verified by:** the annotated handler, and the byte layout read off `gerdep.io` and
`frise.io` matching it -- 21 cases for 21 names, with the live value of global `0x3eac`
equal to 0, 1 and 2 in the three regions visited.

### 7.2h Arrays: how a script reads the world map

The scripts index multi-dimensional arrays, and the world map is one. Three pieces.

**Expression `0x26` -- indexed global byte load** (`vm_expr_load_global_indexed`,
`seg_0000:6b0b`):

```
26 <base:u16>        ->  DX = byte at global[base + index]
```

`mov bp, ss:[0bf6]` takes the global base, `vm_index_byte` computes the element offset,
`mov al, es:[bp] / cbw` returns it sign-extended.

**The array descriptor sits immediately below the data** (`vm_index_byte`,
`seg_0000:6c2e`). For an array at `base`:

| where | width | meaning |
|---|---|---|
| `base-1` | u8 | number of **extra** dimensions -- 0 means a plain vector |
| `base-4`, `base-6`, ... | u16 | the stride for each, innermost last |

AX enters as the base and DX as the last subscript; the rest come off the expression stack
at `SS:BX`. Each round is `sub di,2 / mul word ptr es:[di]`, accumulated in `ss:[0b0a]`.

**The expression stack** is three more opcodes, all in the same block:

| opcode | handler | |
|---|---|---|
| `0x40` | `7140` | push the accumulator (`sub bx,2 / mov ss:[bx],dx`) |
| `0x36` | `7147` | pop it |
| `0x38` | `7150` | evaluate sub-expressions in a loop (`call 069ab / jmp 7150`) |
| `0x3a`, `0xe4` | `7156` | end that loop -- `add sp,2 / ret` discards its return address |

`0x38`'s loop looks like a hang in the listing and is not: the terminator throws away the
return address. It also explains why every breakpoint stop on a map cell reports
`seg_0000:7153` -- that is the loop's return point, with the reading handler already
returned.

**Worked example: the map read.** `lacustre.io` offset 1190, which 23 of 51 genuine stops
on a watched map cell land on:

```
1e                statement: eval_reset
  38              begin an expression sequence
    12 18         byte frame var 24          -- a subscript
    40            push it
    12 19         byte frame var 25          -- the other subscript
    26 80 00      global[0x0080 + index]     -- THE MAP
  3a              end the sequence
```

Base `0x0080` is exactly where `cont*.fic` is loaded (3.12). Its descriptor reads, live:
`global[0x7f] = 1` -- one extra dimension -- and the stride word at `global[0x7c]` = **90**.
So the declaration is `map[54][90]` and the access is `map[row][col]`.

**Verified by:** the three annotated handlers; a MEMORY_READ breakpoint on one grid cell,
which fires at `seg_0000:7153` and nowhere else across two watched cells; and the descriptor
read live, where the stride is the 90 the grid geometry independently requires.

### 7.2f Why some branch targets are wrong: misaligned decodes (T39e)

`0x14` targets land on a valid opcode **178/178 = 100%**, against a chance baseline of
90.2% (231 of 256 byte values are opcodes). `0x0a` manages 87.3% and `0x06` only 72.7% --
*below* chance, which means those sites are not real instructions rather than that their
shape is wrong.

Three measurements say what is happening:

- **The displacement is a signed immediate.** Signed gives 72.7% valid for `0x06`,
  unsigned 52.5%. Not computed, not unsigned.
- **26 of `0x06`'s 27 failures target outside the file entirely**, rather than landing on
  a bad byte inside it. A script call cannot leave its own buffer, so those sites cannot
  be calls.
- **57% of all 47 failing sites have `0x42` as their operand's high byte** -- and `0x42` is
  the *terminator opcode* (7.2c). The decode is eating an opcode as half of a
  displacement, which is the signature of starting a statement at the wrong byte.

**Conclusion: bogus sites, not computed targets.** They are places traversal entered at a
wrong offset, and the target check added in 7.2d already stops them propagating. Count:
47 of 257 `0x06`/`0x0a` sites reached.

**Verified by:** the in-edge search over the whole file; the entry/coverage table above
against `.ish/live-offsets.json` (IP-verified samples); the signed/unsigned sweep; and the
operand-byte histogram.

### 3.16 The small assets are scripts, and the `.fic` files are the data (T29h)

Looking for where monsters live turned up the shape of the data rather than the answer.

**The small `.io` files are script, not tables.** `encont.io` (2,008 bytes), `monstre.io`
(2,016), `telep.io` (2,016) and `dead.io` (448) all begin with the 16-byte asset header and
then **`29 …` — `vm_op_block_init`** — the same opening as `main.io`'s script. So monster
placement, encounters and teleports are *code*, not a lookup table, which is why searching
them for records found nothing.

Sizes cluster: `monstre.io` and `telep.io` are identical in length at 2,016.
`dead.io` and `auteur.io` looked like a third pair at 448 — **they are not**. Both are
65,984 bytes; the 448 was a truncated `u16` read of a 24-bit size field (3.0), and what
follows the short script in each is a whole VGA page (3.18). The "fixed script slots"
reading was wrong: two equal sizes out of 106 is not much of a coincidence.

**None of them names an asset inline.** A scan for opcode `0x45` (`vm_op_load_asset`, a word
id then a NUL-terminated filename -- section 7) finds **zero** instances in `encont.io`,
`monstre.io`, `dplt.io` or `samb.io`, though `main.io` is full of them. Whatever these
scripts refer to, they refer to it by id.

~~**`dead.io` is the death script.** 448 bytes is far too small for the full-screen demon
frame seen when the party is wiped (FINDINGS 4.17), so this is the sequence that shows it,
not the picture.~~ **Struck.** `dead.io` is 65,984 bytes, not 448, and it carries the demon
frame itself — verified 64,000/64,000 against live VRAM (3.18). The argument was sound and
its premise was a decoder bug.

**The `.fic` files are where the fixed data is.**

| file | size | content |
|---|---|---|
| `cont1.fic` .. `cont6.fic` | 4,860 each | **exactly 90 x 54** -- six world grids, confirming T11g's dimensions |
| `en1.fic` | 3,640 | loaded **twice** during setup (4.10); `EN` in a French codebase reads as *ennemis* |
| `tab1.fic` | 361 | only four distinct byte values, 1-4 |

`en1.fic` is zeros for its first 56 bytes and then a run of big-endian words with a zero
high byte -- 15, 32, 28, 7, 11, 50, 20, 20, 20, 20, 20, 20, 20, 39, 31, 12, 7, 10, 9, 9,
40, 31, 46, 26, 33, 37, 38, 20, 29, 22, 6, 27 -- then zeros again. Roughly thirty small
numbers in the 6..50 range, which is the shape of a stat block or a per-entity count, not
of coordinates.

**Status:** structural only. Nothing here yet says *where* a monster stands. The two leads
that remain are `en1.fic`'s word array and the `cont*.fic` grids' cell values (T11g3).

### 3.18 Some assets are whole VGA pages, not sprite chains

`dead.io` and `auteur.io` carry no sprite chain at all. After a short script and a palette
record comes a **320x200 page of 8-bit indices** — 64,000 bytes written straight to
`0xA0000`.

```
0      short script (the usual `29 ...` opening, 3.16)
1192   fe ff 00 00                    palette marker (3.9)
1196   768 bytes                      the palette, 8-bit values
1964   8 bytes                        unread
1972   64,000 bytes                   the page
65972  12 bytes                       trailing
```

The page offset is **`palette_marker + 780`**, not `len(decoded) - 64000`: `dead.io` has 12
bytes after the page, and anchoring on the end of the blob puts every row 12 bytes late,
which drops the match to 32.6% while still looking approximately right when rendered.

| asset | page | what it is |
|---|---|---|
| `dead.io` | 1 | the demon frame shown when the party is wiped — `captures/pages/dead-page0.png` |
| `auteur.io` | 1 | the credits card — `captures/pages/auteur-page0.png` |

**This is not a general rule.** Assets that *do* have a sprite chain also carry palette
records, and anchoring a page off one of those gives noise — `presen.io`, `iboishar.io` and
`stage.io` were each rendered that way and each produced static. Check that `tools/ioscan.py`
finds zero sprites before believing a page. `tools/fullscreen.py` renders them.

**Status:** established for `dead.io`; `auteur.io` by the same layout and legible output.
**Verified by:** `dead.io`'s 64,000 bytes compared against the emulator's framebuffer at
`0xA0000` with the demon frame on screen — **64,000 / 64,000 identical**. The offset was
found by sweeping alignments, which is also what exposed the 12-byte tail.

### 3.19 `theend.io` is a bare 4bpp raster, 288 pixels wide

Not a sprite chain and not a VGA page: **`theend.io` is raw 4bpp pixels at a 144-byte
stride**, starting right after the 16-byte asset header, with no per-image headers at all.

| | |
|---|---|
| pixel depth | **4bpp.** 78.7% of its bytes have equal nibbles, against 6.25% for random data, 53.6% for `logo.io`, 59.0% for `buste.io` -- and 25.5% for the 8bpp `dead.io` |
| stride | **144 bytes = 288 pixels.** Row-to-row agreement peaks hard at 144 (0.768) against 0.61 at 143 and 145. The same sweep returns 144 for `logo.io`, whose width is already known -- the control |
| extent | ~992 rows from offset 16, with **one** internal discontinuity at row 599 and noise in rows 0-10 |
| palette | **none.** It is the only asset in the corpus with no `fe ff 00 00` record (3.9), so its colours come from elsewhere, as the presentation screens' do |

Rendered with an invented ramp the content is plainly a colonnade -- pillars, a floor,
figures between them (`captures/pages/theend-rows{000-200,300-500}.png`, gitignored like
every other decoded-asset render). That is what an ending sequence in this game would look
like, and it is why nothing found it earlier: `tools/ioscan.py` only looks for sprite chains,
and there is no chain to find.

**Status:** geometry and depth established; palette and block structure are not. Whether
rows 11-599 and 600-991 are one tall scrolling backdrop or several stacked frames is open.
**Verified by:** the equal-nibble ratio against three assets of known depth; the stride
sweep with `logo.io` as a known-good control.

### 3.19b `iboishar.io` is still unread

132,728 bytes, the largest asset in the game. Not a sprite chain (`tools/ioscan.py` finds
zero), not a VGA page (3.18 renders static at every anchor), and **not a raster at any
stride** -- the sweep that isolates 144 for `theend.io` and `logo.io` finds no peak for it at
all (best 0.43 at 256, with every neighbouring stride within 0.02). It carries three palette
records, at 62,445 / 77,192 / 78,295, so parts of it are picture-adjacent, and its
equal-nibble ratio of 51.8% is consistent with 4bpp somewhere inside.

Tracked as **T47**.

### 3.17 Where on-screen positions come from (T40)

Every coordinate in FINDINGS 4.15 was measured off a framebuffer. This is the derivation.

`sprite_dest_compute` (`seg_0e97:0371`) turns a sprite's coordinates into a destination
pointer:

```
les di, ss:[1dbf]     ; destination base -- the offscreen buffer
mov ax, ss:[0c2e]     ; Y
mov bx, ss:[1dd5]     ; stride, bytes per row
mul bx                ; Y * stride
add di, ax
add di, ss:[0c2c]     ; + X
```

**dest = base + Y x stride + X**, with the coordinates held in two engine variables:

| variable | meaning | read live |
|---|---|---|
| `ss:[0c2c]` | **X** | varies per sprite |
| `ss:[0c2e]` | **Y** | varies per sprite |
| `ss:[1dd5]` | stride | `0x0140` = **320** |
| `ss:[1dbf]` | destination base | `0000:e000` -- the back buffer `blit_to_screen` copies to VRAM (3.13d) |
| `ss:[0c30]` | a clip/origin offset subtracted at `038b` and `03a3` | 15 |

**Checked against the one position that was already proven.** Polling `ss:[0c2c]`/`ss:[0c2e]`
while the party panel redraws produces **x=0, y=147** among its samples -- exactly the
portrait origin established byte-for-byte against VRAM in 3.13b. The position is therefore
*derived* now, not measured.

Other UI positions seen in the same poll, which are the rest of the panel: (0,139),
(24,157), (0,175), (14,199), (31,152), (19,157), (24,152).

**Who writes them, and what that means for layout (T40c).** Two things, and the second is
the answer a rewrite needs.

*They are a bounding box, not a plain x/y.* `draw_bbox_reset` (`seg_0000:4179`) sets
`ss:[0c2c]`/`[0c2e]` to `0x7fff` and `ss:[0c30]`/`[0c32]` to `0x8000` -- +MAX and -MAX,
the standard min/max initialisation -- and `41db`/`41f8` are `cmp`/`mov` min updates. So
`0c2c`/`0c2e` are the **top-left of the current draw rectangle** and `0c30`/`0c32` the
bottom-right. That is why `sprite_dest_compute` adds them as the origin, and why polling
them during a redraw yields each element's own position.

*Layout is data, carried per entity.* `draw_pos_from_entity` (`seg_0000:469a`, and again at
`4768`) reads the coordinates out of a record and writes them to the draw origin, clamped
to the clip bounds in `ss:[0c62]`/`[0c64]`:

```
mov cx, [di+0ch]  /  mov ss:[0c2ch], cx      ; X
mov cx, [di+0eh]  /  mov ss:[0c2eh], cx      ; Y
```

So a drawable's position lives **in its own record at +0x0c and +0x0e**, not as a constant
in the code. And the records are built by the script: `vm_op_declare_entity` (opcode `0x46`,
`seg_0000:2ded`) copies a **32-byte inline record** out of the script stream into a
structure at `es:[bx+6]` (7.4) -- the same kind of structure these offsets index.

**So a rewrite should read panel layout from the entity records rather than hardcode it.**

**But the panel's entities are not declared in `main.io` (T40d).** Traversing the whole
reachable script finds **8** `0x46` statements, and six of them are misaligned decodes --
their ids read 3840, 12311, 30720 and their records are noise. Only the two at the entry
point are genuine, and both look like **rectangles** rather than sprite positions:

| at | first pair | second pair | tail |
|---|---|---|---|
| 24 | (127, 86) | (255, 125) | `0,0,0,0xff00,255,1,0,0xff00` |
| 60 | (0, 199) | (319, 199) | identical |

(319, 199) is the bottom-right of a 320x200 screen, so these read as clip or viewport
rectangles -- plausibly the 3D view and a full-width strip -- not as the portrait or the
frieze.

Neither candidate reading of the record lines up with a polled position either: taking
`+0x0c` as record byte 6 gives X = 86 and 199 with Y = 0 for both, and taking it as record
byte 12 gives (255,125) and (319,199). None of those appears among the positions polled
during a panel redraw.

**The entity block is located and the mechanism confirmed (T40d).** `ss:[0bf6]` is a far
pointer, read live as **`126b:02a0`**, and a declaration's word operand is the index into
it: `vm_op_declare_entity`'s handler does `lodsw / mov bx,ax / add bx,ss:[0bf6] /
or es:[bx],40h`, so `main.io`'s first declaration -- operand **14** -- owns the structure at
block offset +14. Dumping that block from a running game shows both of `main.io`'s records
sitting there verbatim: `(127,86)` and `(255,125)` at +24 and +32, `(319,199)` at +84.

**But the panel is not drawn from entity records.** The block is **zero beyond +128** -- only
those two entities exist -- and no `(x,y)` pair anywhere in it matches a position polled
during a panel redraw. Nor does any byte offset in the `0x46` records of `frise.io` (20
declarations, now reachable), `buste.io` (29) or `main.io` (8).

So `draw_pos_from_entity` serves those two rectangle entities, and the panel's sprites get
their position elsewhere. **T40e traced that path:**

*Which routines run.* A call-count diff of an ACTION-menu draw against an equal idle window
(no breakpoint, so the draw actually happens) moves exactly three functions in this region,
all with **0** idle calls: `seg_0000:4535` (**306** calls, containing the clamped writer at
`469a`), `seg_0000:4723` (**153**, containing the unclamped pair at `4768`) and
`seg_0000:4170` (**153**, containing the bounding-box reset at `4179`).

*Where their operand comes from.* Both writers take **`DI` as an input** -- they read
`[di+0ch]`, `[di+0eh]`, `[di+10h]` in their first instructions and never set `DI`
themselves. The caller at `seg_0000:3f83` supplies it:

```
mov di, es:[bx+2]     ; the pointer stored at entity+2
```

and `es:[bx+2]` is exactly where `vm_op_declare_entity` writes a pointer. So the chain is:

**script declaration -> entity structure (at `ss:[0bf6]` + id) -> pointer at +2 -> an
instance -> `+0x0c`/`+0x0e` are the X and Y the blitter uses.**

*Where the instances live.* The `0x46` handler allocates them from a free list: `lds di,
ss:[0be8]` / `add di, ss:[0bec]` / `mov ax,[di+4]` / `mov ss:[0bec], ax`. Read live, the
pool is at `1848:0000` with the free head around `0x0b70`, so ~2.9 KB of instances are in
use during play.

**So panel layout is runtime state, not a constant in the file.** A rewrite cannot read the
portrait's (0,147) straight out of an asset; it has to model the entity/instance structures
and whatever initialises their position. That is a sharper answer than 3.17's earlier
"layout is data" -- the *record* is data, but the *drawn position* is a field of a
runtime instance.

**The instance structure (T40f).** Following one entity rather than scanning the pool
settles the layout. `main.io`'s first declaration carries operand **14**, so its entity sits
at `ss:[0bf6] + 14` = `126b:02ae`, and the pointer at +2 is an offset **into the pool
segment** (`lds di, ss:[0be8]` then `mov es:[bx+2], di`), not into the entity segment --
reading it in the wrong segment yields x86 code and nonsense coordinates.

| instance field | meaning |
|---|---|
| +0 | flags (the `or es:[bx],40h` bit) |
| +1 | the declaration's byte operand |
| **+4** | **next instance** -- `0x0074` -> `0x009a`, which is **+38** |
| +6 | a second pointer |
| +0x0c / +0x0e | **X / Y**, what the blitter uses |
| +16 | `0x7fff`, the bounding-box sentinel |
| +22..25 | the record's second coordinate pair |

**Instances are 38 bytes**, established from the `+4` chain rather than from a scan. And
+22..25 carries each record's second pair verbatim -- `(255,125)` for `main.io`'s first
entity, `(319,199)` for its second -- which independently confirms the instance is built
from the script record.

**What the positions are.** Walking the chain at stride 38 gives `+0x0c`/`+0x0e` values of
(9,6), (40,94), (71,10), (74,84), (100,87), (124,85), (128,85), (146,81), (166,85),
(171,87), (199,85), (203,85), (248,74), (258,85), (265,76), (272,86) -- x from 9 to 272 and
y from 6 to 94, which is the **viewport**, not the panel.

**Still open:** none of those matched a position polled from `ss:[0c2c]` during a panel
redraw. So the instances carry *viewport object* positions, and the panel chrome is
positioned by something else again. The chain and the structure hold; which mechanism
places the panel does not follow from them.

**Verified by:** the instruction sequence above read from `ishar-listing.txt`; the three
constants read live from a running game; the x=0,y=147 sample matching 3.13b's
framebuffer-verified origin.

### 7.7 Entry point sets, found by polling (T37f)

T37's blocker was that embedded scripts have no known entry point. They have several each,
and they can be found without a breakpoint.

**The method: poll, do not break.** A breakpoint on `vm_run` costs ~2.6 useful stops/s and
drowns in ~340 background stops/s, which stalls the game. Polling `read_cpu_state` runs at
**~3,550 samples/s** with the game unaffected. `SI` is only the script program counter
while the CPU is inside `vm_run`'s fetch loop, so samples are kept only when
`CS == load` and `IP` is in `0x26eb..0x26f8`; without that filter the poll attributes any
moment `SI` happens to point into an asset buffer -- a string move, a block copy -- which
is not execution at all. One 215s cold-start run gave 765,027 samples, **15,555 of them
inside `vm_run`**, across 19 assets.

**Entry sets, and what they cover.** Starting from the lowest observed PC and adding any
observed PC the traversal still misses:

| asset | entry set | observed PCs covered | bytes reached |
|---|---|---|---|
| `frise.io` | 478, 27826, 29024, 32526 | **41/41** | 68.7% |
| `dplt.io` | 203, 249, 448, 1008, 3217, 3232 | **26/26** | 70.3% |
| `samb.io` | 111, 213, 269, 428, 571, 1271 | **18/18** | 7.3% |
| `geren.io` | 55, 85, 238, 931, 5387, 5402 | **29/29** | 35.2% |
| `param.io` | 1794, 4183, 6640, 8600, 10955, 11245 | **18/18** | 63.0% |
| `affobj.io` | 51, 65, 165, 548 | **17/17** | 62.6% |
| `encont.io` | 47, 91, 116, 155, 291, 451, 805 | **24/24** | 67.3% |

`affobj.io` was at 0% accounted for and is now **62.6% reachable script** -- which is what
T33 was asking for. `param.io` and `encont.io` were also at 0%.

**An asset has a set of entries, not one.** Traversing from offset 24 -- `main.io`'s loader
entry -- reaches **0%** of observed execution in `frise.io`, `dplt.io`, `samb.io`,
`gerdep.io`, `encont.io`, `souris.io` and `affobj.io`. The idea of a universal entry offset
is dead, and 7.6's negative result on it stands.

**What these offsets are, precisely.** Each is an offset at which the VM was *observed
executing*, and the set is the smallest one whose traversal explains every observed PC. That
is a weaker claim than "the engine enters here": a polled first-sighting is an upper bound,
since polling can miss the true first statement -- `logo.io` reads 68 here against the 24
established by breakpoint in 7.5. They are sound as *traversal seeds*, which is what a
disassembler needs.

**Verified by:** `.ish/t37f.json` and `.ish/t37f-entries.json`; the `CS`/`IP` filter; and
`main.io` coming out at exactly **24**, its independently established entry.

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

**RETRACTED: the "ten assets" result below is invalid (T39b).** The cheap probe it rests
on cannot be trusted, and the check that shows it is one line: at a `MEMORY_WRITE` stop on
the PC slot, does the slot actually contain `SI`? **4 stops agreed and 5,868 did not** --
the slot sat constant at `0x144d` while `SI` wandered over `0x6f37`, `0x72ed`, `0x715e`.
So `DS:SI` read at such a stop is not the script PC, and every offset and asset name that
probe produced is meaningless.

This is the "any pause reaches the GDB client" scar in a form the usual guard misses: an
execution breakpoint can be validated by comparing `ip` to the armed address, and a
memory breakpoint cannot. The replacement guard is the one above -- **read the watched
location and check it holds what the register says**.

What survives is the IP-verified work: `main.io`, `logo.io` (entry 24 each, first-entry
from a paused cold start) and `frise.io`, `dplt.io`, and `samb.io` from gameplay scans, all
taken at a `vm_run` breakpoint where `r["ip"] == entry` was checked. **Five** assets, not
eleven.

It also resolves 7.2c's puzzle: the "first yield" offsets were never yields, so there was
never a reason for them to follow a `0x42`. And separately confirmed while chasing it, the
`DS:SI` -> offset mapping itself is exact -- across 10 IP-verified samples the matched
index equalled `SI` every time, so `offset = SI` and the base is `DS*16`.

**Superseded text follows.**

**Ten assets, not three (T37c).** A cheaper instrument widened this considerably. Breaking
on `vm_run` stops once per *statement* -- its loop jumps back to its own entry -- which
costs so much that the game stops advancing at all: 270s of wall clock with the screen
frozen and 0.0% of pixels changed. But `mov es:[bp-8], si` at `seg_0000:26b2` runs only
when `vm_run` **returns**, so a `MEMORY_WRITE` on the script-PC slot fires once per script
*yield* instead: **164 stops/s against 2.6**, and the game runs.

Driven from boot to the intro, ten assets were seen running script:

`main.io`, `logo.io`, `blancpc.io`, `itaverne.io`, `preson.io`, `presen.io`,
`presti.io`, `param.io`, `fond.io`, `gerdep.io`

`blancpc.io` is the blank frame, `fond.io` a backdrop, `presti.io` the title lettering --
all previously filed as pure graphics. Whatever the other 58% of asset bytes are, script
is a large part of it.

**Status:** partial, and the entry-point question is still open. The offsets that scan
reports are **yield points, not entries**: `main.io` shows 256 there and 24 from a paused
cold start, so the first yield caught depends on when the probe attached. `frise.io` and
`dplt.io` did not appear at all in that window. Only `main.io` (24) and `logo.io` (24)
have entry points, both from a paused cold start where the first `vm_run` entry is the
entry by construction.

The slot is at a fixed linear address (`ES:BP = 126b:02a0`, so `0x12948`) and is stable
across runs, which is what makes the cheap probe possible.

**Why entry points need the interpreter, not more tracing (T37e).** A genuine cold-start
run of the cheap probe gives each asset's *first yield*: `main.io` 256, `logo.io` 256,
`blancpc.io` 801, `fbuis.io` 3960 (an eleventh asset running script). For `main.io` the
entry is independently known to be 24, so the obvious corroboration is to step from 24 and
see whether the walk passes through 256. It does not -- and neither do the others.

That is not a tuning problem. `tools/vmi.py` walks **linearly**, and a script reaches its
first yield through jumps; `main.io`'s walk covers offset 758 without ever touching 256.
So a first yield cannot be tied back to an entry until the stepper follows control flow,
which needs the branch conditions evaluated, which is T39b.

Three approaches to entry points have now failed, and they fail for different reasons
worth keeping:

- **Static.** `es:[bp-8]` has six sites; the three writes are all script-level call/return
  (`add ax,si`), and nothing writes the segment half at `bp-6`.
- **Filter by segment.** Assets share the script buffer (`DS = 1cf3`), so excluding
  `main.io`'s segment excluded every script. Verified against a control condition that
  does fire.
- **Corroborate a yield by stepping.** Blocked on linear walking, above.

The one method that works is the expensive one: from a paused cold start, a `vm_run`
breakpoint catches every statement in order, so the first is the entry by construction --
which is how `main.io` and `logo.io` were both established as 24. It costs 2.6 stops/s and
stalls the game before the later assets load.

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

**Verified by:** live VRAM at `0xA0000` with the game in Fragonir, compared against the
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

Two independent per-row deltas. Sampled live while walking in Fragonir: `cs:[002c] = 15`,
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

## 7.9 When each script starts, and what `encont.io` turns out to be (T44)

Polling `DS:SI` from a paused cold start timestamps the first execution of every script,
which separates the boot scripts from the gameplay set cleanly:

| t | asset |
|---|---|
| 57.5s | `main.io` (offset 24 -- the entry, 7.5) |
| 58.5s | `logo.io` |
| 78.0s | `presen.io` |
| 91.1s | `presti.io` |
| 115.5s | `param.io` |
| 116.9s | `buste.io` |
| **123.0-123.3s** | `arbre`, `samb`, `plaine`, `rplaine`, `dplt`, **`encont`**, `affobj`, `frise`, `geren`, `gerdep` -- **all within 0.3s** |
| 124.4s | `lacustre`, `souris` |

**Ten scripts start together** when the game proper begins, and `encont.io` is one of them --
so it is **part of the gameplay script set, not a special-occasion handler**.

**But it does not run during play.** Windows covering idle, walking, turning and approaching
an NPC attribute 1,400-2,400 samples each, and `encont.io` appears in **none** of them:

| asset | idle | walk | turn |
|---|---|---|---|
| `gerdep.io` | 690 | 666 | 647 |
| `frise.io` | 345 | 349 | 357 |
| `geren.io` | 158 | 145 | 153 |
| `dplt.io` | 79 | 107 | 89 |
| `plaine`/`arbre` | — | 46/38 | 64/63 |
| **`encont.io`** | **0** | **0** | **0** |

It starts with the others, then waits for something none of those actions triggers. That is
**consistent with** the *encounter* reading and **does not establish it** -- "starts at
gameplay, then stays quiet" fits several roles.

**Two findings from the same measurement.** `gerdep.io` is the busiest script in the game,
running constantly at about twice `frise.io`'s rate -- and `gerdep` reads as *gérer
déplacement*, which constant execution during movement supports without proving. And
`plaine.io`/`arbre.io` execute **only when the view changes**, so scene assets carry
per-scene script that runs on redraw, not just pixels.

**Verified by:** `tools/t37f-poll.py` first-execution timestamps from a paused cold start;
`tools/t44-when.py` attributed-sample counts over four action windows.

## 7.8 What the small logic scripts do, and what `encont.io` is not

With entry sets in hand (7.7) the small scripts disassemble. `tools/vmi.py <asset> --listing`
now reads the entry set for any asset that has been observed executing.

**They share a template.** `encont.io` and `affobj.io` both begin with **47 bytes that are
never reached**, then the same opening: `32 02 00` (`vm_op_jump_rel16`), a `00`, then
`08 fa` (`vm_op_jump_byte`) branching back, then a `0a 01 00` jump forward. Byte for byte
the same shape in two unrelated files, so the first ~50 bytes are a header plus a standard
entry stub rather than content.

**They are logic, not loaders.** Opcode profiles over the reachable statements:

| | statements | `0x45` load_asset | `0x29` block_init | top opcodes |
|---|---|---|---|---|
| `main.io` | 5,433 | **115** | **118** | `00`, `42`, `3a`, `14`, `08` |
| `encont.io` | 618 | **0** | 0 | `00`, `1e` eval_reset, `14` jump_if_zero, `3a` |
| `affobj.io` | 397 | **0** | 0 | `14` jump_if_zero, `00`, `1e`, `3a` |
| `dplt.io` | 1,084 | **0** | 0 | `00`, `3a`, `1e`, `12` |

`main.io` is the only one that loads assets or initialises blocks -- it is the program that
sets the game up. The others are dominated by conditional branching (`0x14`) and expression
evaluation (`0x1e`, `0x1f`), which is the shape of decision logic operating on engine state.

**`encont.io` is undocumented, and its name is a guess.** It has no section in this file and
never has; it appears only in lists. The reading "*encontre* = encounter" is a **pun on the
filename**, not a finding, and nothing in its disassembly supports it yet: no asset loads,
no distinctive constants, and a statement mix nearly identical to `dplt.io`'s. What is
established is only: 2,008 bytes, loaded during engine setup (FINDINGS 4.10), script rather
than a table (3.16), 1,376 bytes reachable from entries `[47, 91, 116, 155, 291, 451, 805]`.

**A correction this produced.** Opcode `0x15` was named `vm_op_attack_swing` in T29f after it
spiked to 7,805 calls during an attack. Static disassembly finds it **8 times inside
`affobj.io`**, the object-display script. It is renamed `vm_op_15`: a call count that spikes
during one action does not make the opcode that action's own.

## 8. `affobj.io`, byte by byte

730 bytes on disk, 1432 after decoding. Asset **id 7**. The name reads as *affichage
objet* -- object display.

### 8.0 What is in it: four handlers over a 2x2 condition (T44 pre-work)

Section 8 established what `affobj.io` **is** -- VM bytecode, not sprites, palette, table or
text. With its entry set `[51, 65, 165, 548]` (7.7) it now disassembles, and its **shape** is
visible: **397 statements, 913 of 1,432 bytes reachable**, no asset loads, and a profile
dominated by `vm_op_jump_if_zero` (57) and expression evaluation -- decision logic, not
loading.

**It is four near-identical handlers.** The 8-byte sequence at offset 165,
`1f 38 14 2c 26 86 14 4a`, occurs **exactly four times** -- at 165, 291, 417 and 548 --
spaced 126, 126 and 131 bytes. Two of those offsets are themselves entry points, so the
engine enters different handlers for different cases.

**They vary on two independent binary parameters.** Comparing the four 120-byte blocks, 37
positions differ, and they fall into two clean patterns:

| pattern | positions | distinguishes |
|---|---|---|
| `A B A B` | +21, +22, +25, +60, +61, +64 | blocks 1,3 vs 2,4 |
| `A A B B` | +13, +39, +52, +82, +94..+102 | blocks 1,2 vs 3,4 |

Two binary conditions, 2x2 = the four blocks. So `affobj.io` is a small decision routine
instantiated four times over a pair of two-valued parameters -- consistent with the name
*affichage objet* and with an object being displayed in one of two states in one of two
places, though **which two conditions is not established**: that needs the expression
operands decoded, since the differing bytes are operands to `0x14`/`0x1f`.

**What the handlers actually do.** Reading the opcodes the file leans on gives the
behaviour, not just the shape:

| opcode | handler | effect |
|---|---|---|
| `0x4e` | `seg_0000:325f` | takes an **entity id** inline and does `and es:[bx+di],0bfh` -- `0xbf` is `~0x40`, and `0x40` is exactly the bit `vm_op_declare_entity` **sets** at `or es:[bx],40h`. So it **clears an entity's active/visible flag** |
| `0x52` | `seg_0000:48bd` | sets a frame word `es:[bp-1ah]` to `0xffff` |
| `0x62` | `seg_0000:58a1` | clears bit 0 of the frame byte `es:[bp-24h]` |
| `0x3a` | `seg_0000:2e94` | clears `ss:[0c37]` |
| `0x40` | `seg_0000:2ce2` | zeroes `ss:[0c6a]`/`[0c6c]`/`[0c6e]`, then a lookup returning `-1` on failure |

So `affobj.io` **tests conditions and turns object entities on and off**: `0x40` is an
entity's active bit, set when the script declares it and cleared by `0x4e` here. That is a
behavioural statement rather than a reading of the filename, and it fits *affichage objet*.

### 8.0b What the four blocks actually differ by (T45)

With expressions rendered (6.1b) the four blocks can be read side by side. They are **not**
four cases of a condition the script tests -- they are four variants that differ by **which
optional statements they execute**, along two independent axes:

| axis | variant A | variant B |
|---|---|---|
| 1 | `0x04` -- handler is `seg_0000:0022`, a bare **`ret`**: a no-op | `0x82` -- evaluates **two** expressions and discards them (side effects only) |
| 2 | `0x52` -- sets the frame word `es:[bp-1ah]` to `0xffff` | `0x54` -- copies `es:[bp-3]` to `ss:[0c70]`, then two evaluated expressions into `ss:[0c6a]` and `ss:[0c6c]` |

Blocks 1 and 3 take variant A on axis 1, blocks 2 and 4 take B; blocks 1 and 4 take A on
axis 2, blocks 2 and 3 take B -- which is the `ABAB`/`AABB` split the byte diff showed.

**What all four share** is the substance:

- they read entity fields through statement `0x38`, whose handler evaluates three
  expressions and then indexes `ss:[0bf6]` -- the **entity block base** (7.5). The rendered
  operands are `e38[wordvar[44]]` and `wordvar[46]`, so variables **44** and **46** hold the
  entity references this file works on;
- they branch on those values;
- they call **`vm_op_entity_clear_active`** (`0x4e`), clearing the `0x40` visible bit that
  `vm_op_declare_entity` sets.

So `affobj.io` reads two entity references out of engine variables 44 and 46, tests them,
and switches object entities off -- with four variants differing only in whether an extra
pair of expressions is evaluated and whether a frame flag or three engine words get set.

**Not established:** the game-level meaning of the two axes. `ss:[0c6a]`/`[0c6c]` are the
same words statement `0x40` zeroes before a lookup, which hints at a search parameter, but
that is a lead rather than a finding.

**Verified by:** the byte search for the block signature; the position-by-position diff of
the four blocks; the opcode profile over statements reached from the entry set; the `0x40`
bit being set by opcode `0x46` and cleared by `0x4e` against the same `ss:[0bf6]`-based
entity block; and the four handlers above read from `ishar-listing.txt`.

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
traced with `tools/gdbtrace.py --drive`, each ending in the Fragonir outdoor scene
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

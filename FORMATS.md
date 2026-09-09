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

A byte-oriented **RLE decoder** sits at `seg_0000:7a79` with its stream helpers:

| address | name | what it does |
|---|---|---|
| `seg_0000:7a79` | `rle_decode_loop` | one pass per plane; `ss:[0b18]` counts planes down |
| `seg_0000:7ade` | `get_byte` | next input byte, refilling when `BX` reaches `ss:[0b3a]` |
| `seg_0000:7aee` | `read_next_chunk` | refill: 0x1f40 (8000) bytes into the buffer at `ss:[0b5a]` |
| `seg_0000:7b06` | `put_byte` | write one byte to `ds:[si]`, bounds-checked |

Plane count comes from `ss:[0b57]`: `0x80` → 1 plane, `0xa0` → 2 (with a special path
at `0x7b85`), anything else → 8. A control byte below `0x80` is a literal run of `c+1`
bytes; `c >= 0x80` takes the branch at `0x7aa3`, not yet read.

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

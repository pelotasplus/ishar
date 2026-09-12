# REBUILD.md

    0  Read an asset        the container every .io is wrapped in
    1  Sprites              the chain, the five pixel modes, drawing 4bpp
    2  Palettes             the record, the 16-colour groups
    3  The UI chrome        panel, action bar, life bars, portraits, and where they go
    4  The world map        the 90x54 grids, the party's position, what a cell means
    5  The 3D viewport      why it is not a blit, and what is still missing
    6  Text                 the four languages
    7  The script VM        what is code rather than data, and what that costs you
    8  How much is proven

---

## 0. Read an asset

The game's data lives in 98 `.io` files. Each one is a single compressed blob with a small
header.

### The header — the first 6 bytes

    offset  size  field
    0       3     decoded size, little-endian
    3       1     compression mode
    4       2     directory flag

**Decoded size** counts the header too, so the payload you will produce is smaller than
this number.

**Compression mode.** Mask it with `0xFE`, then:

    0xA0   LZ77-style bitstream    97 of 98 files
    0x80   RLE
    0x00   stored, no compression  (blancpc.io only)

**Directory flag.** When it is zero, 16 more bytes follow the header before the compressed
data starts. Only 5 files have one. So the header is 6 bytes long, or 22 when the flag is
zero.

Now you have both numbers you need:

    decoded payload size = decoded size - header length

Decompress everything after the header. `tools/io.py` has all three decoders, checked
byte-for-byte against the running game.

### Trap: the size is 24 bits, not 16

Nine files decode to more than 64 KB. Read the size as a 16-bit word and those nine
truncate silently — `dead.io` becomes 448 bytes of a 65,984-byte file, and nothing errors.

### What you get back

The decompressed payload starts with its own 16-byte header:

    offset  size  field
    0       2     asset id — what scripts use to refer to this file
    2       6     always 16 00 00 17 00 00
    8       8     unknown

Sprites, palettes and script bytecode follow.

---

## 1. Sprites

Most art assets put script bytecode straight after the 16-byte header, then a run of
sprites stored back to back. There is no index — you walk the chain.

### One sprite

    offset  size  field
    0       2     mode, in the low byte
    2       2     width  - 1
    4       2     height - 1
    6       2     palette base, in the low byte

Pixel data follows the header immediately.

    bytes per row = ceil(width / 2)   for 4bpp
                  = width             for 8bpp

    record size   = header size + bytes per row * height

The next sprite's header begins right after that. Keep walking until the next header does
not make sense.

### Trap: a file holds several chains, not one

When a chain ends, more sprites usually follow after a gap.

`frise.io` has five chains. The fourteen sprites in the first one are not the panel — the
panel is in the fifth, at offset 51456, nine thousand bytes past where the first chain
stops.

Walking only the first chain finds 12% of that file. Walking all five finds 30%. Across all
98 assets it is 36% against 48%.

So: when a chain ends, scan forward for the next valid header and keep going.

### The five modes

The mode byte decides everything else about the sprite.

    mode  bpp  header  palette base   transparent
    0x00  4    6       forced to 0    nibble == 0
    0x10  4    8       from word 3    nibble == 0
    0x12  4    8       from word 3    nothing, opaque
    0x14  8    8       0              index == 0
    0x16  8    8       0              nothing, opaque

Mode `0x00` has a **6-byte** header — it has no palette-base field.

A single file can mix modes.

### Drawing a 4bpp sprite

Each byte holds two pixels, **high nibble first**.

The colour index on screen is `palette base + nibble`.

### Trap: test the nibble, not the index

Transparency is decided on the raw nibble, before the base is added. If you test the final
index instead, you punch holes in the sprite wherever `base + nibble` happens to land on 0.

This was got wrong here for weeks and it looks like a palette fault, not a transparency
fault.

### Not known

In several assets the chain stops early and a different kind of record begins.
`marchand.io` accounts for only 3.8% of itself this way. Nobody knows what that second
record type is.

---

## 2. Palettes

A palette is stored as a marker followed by 256 colours.

    FE FF 00 00    marker
    768 bytes      256 x (red, green, blue), one byte each

Store the values as they are. The VGA hardware wants 6-bit channels, so the game shifts
each byte right by 2 on its way out — that shift is an output detail, not the format.

### Palette groups

A 4bpp sprite only uses 16 colours, so its `palette base` says which 16-colour slice of
the 256 it lands in.

`geren.io` holds a bank of 16 such slices.

    base 208  = group 13
    base 192  = group 12
    base 176  = group 11

The same sprite data drawn at a different base comes out a different colour. The game uses
this deliberately — see section 3.

### Trap: the marker is not proof

`FE FF 00 00` occurs freely inside 4bpp pixel data. It appears 80 times across the game
and only **17** of those are real palettes.

Require the whole 768-byte record to fit inside the file, and corroborate with something
else, before believing one.

### Not known

Which palette belongs to an asset that carries none of its own. Several assets rely on a
palette loaded earlier by a different file.

---

## 3. The UI chrome

This is the smallest thing you can put on screen that looks like Ishar.

### Two assets hold all of it

    screen region                        asset       palette base
    right panel: compass, dial, DISK     frise.io    208
    ACTION / ATTACK bar                  frise.io    192 and 176
    LIFE bars                            frise.io    192
    character portraits                  buste.io    208

All of it is 4bpp.

`frise.io` is drawn three times at three different bases. Same pixels, three colour
schemes — that is what the palette base is for.

### Where each piece goes

Positions are **not stored in any file**. At runtime a script creates a structure for each
drawable thing, and the X and Y live in that structure.

Two are confirmed against the game's own video memory:

    asset      offset   size      mode   base   drawn at
    frise.io   51456    32 x 126  0x10   208    (288, 0)    the right panel column
    buste.io    6986    64 x 36   0x10   208    (0, 147)    the leftmost portrait

The panel sprite matches on 97 of its 126 rows. The rows that differ are the ones the game
draws over afterwards: the region caption at rows 2-9, the compass needle and its letters
at 22-51, and the DISK button at 52-65.

These positions are also real, read out of a live redraw, but not yet matched to a sprite:

    (0, 139)    (24, 157)    (0, 175)    (14, 199)
    (31, 152)   (19, 157)    (24, 152)

### How a frame is put together

Everything is drawn into an off-screen buffer, then the whole buffer is copied to video
memory in one go.

    destination = buffer + y * 320 + x

### Not known

The seven unmatched positions above.

---

## 4. The world map

The world is stored in `.fic` files, which are **not** the container format from section 0.
They have no header and no compression — the bytes are the data.

### The grid

    cont1.fic .. cont6.fic     4,860 bytes each
    90 columns x 54 rows       one byte per cell

    cell(row, col) = file[row * 90 + col]

Six files, one loaded at a time.

### Where the party is

Two bytes hold the party's position, and they sit immediately after the grid in memory.

    party row = the byte after the last grid byte
    party col = the byte after that

### Where the game starts

A new game begins in `cont1.fic`, at **row 11, column 29**, in region 0, FRAGONIR.

That cell's value is `0x00`. An NPC stands a few steps north; walking into him opens a
text panel rather than a fight.

Observed on two separate cold boots. It is also where the party is put back when the game
resets it — see below.

### Movement

Movement is **absolute**: the four arrow keys are north, south, east and west. The party
never turns.

There is a facing — the ACTION menu's ORIENTATION verb reports which region lies in it —
but the arrow keys do not change it and nothing found so far sets it.

### What a cell value means

Bit 6 splits the value space cleanly.

    value & 0x40 == 0    a per-cell object marker: which tree, which bush.
                         About 50 such values, roughly 25 cells each.

    value & 0x40 != 0    area terrain, in large blobs.

Specific values that are known:

    0xCC, 0xCD    water. Impassable.
    0xCE          shoreline. One cell wide, encloses each landmass.
    0xE6          impassable.
    0x9D          the inside of a building. cont2 has a walled town,
                  cont5 is almost entirely one fortress.
    rare high     an individual building. Walk up to one and a door fills the view.

### Trap: the meaning of a value is per region

Only five byte values occur in all six grids. Each region has its own set.

A single global lookup table will be wrong.

### Regions

A region is a named area **inside** a grid, not a separate file. There are 21 of them —
FRAGONIR, ANGARAHN, OSGHIROD, and so on through ISHAR and L'OCEAN.

Six grid files. Twenty-one regions.

### Trap: the world is gated

Walk far enough from the start and the game reloads the scene and puts the party back at
row 11, column 29.

Seen three times: twice heading north from `(13, 57)`, once heading west from `(39, 25)`.
The cells involved are ordinary `0x00` — this is a script gate, not terrain, so you cannot
predict it from the map.

The same reset happens if you attack a friendly NPC.

### Not known

Which sprite a cell value draws. There is no table — a script decides, in bytecode.

For the same reason, whether a cell blocks movement is not a function of its value alone.
The same value blocks in one place and not another.

How a coordinate maps to a region.

---

## 5. The 3D viewport

This is the least understood part of the game.

### It is not a blit

The viewport has its own drawing routines. They walk the source sprite and the destination
buffer with two **independent** per-row steps.

Sampled from the running game: source advances 15 bytes per row, destination advances 321.

A destination step of 321 on a 320-wide buffer shifts every row one pixel sideways. That
shear is where the perspective comes from. The source step controls how fast the sprite is
consumed, which is where the size change comes from.

### What follows from that

Viewport pixels are sheared and row-skipped, so **they never appear verbatim in any file**.

Matching the framebuffer against asset bytes finds nothing here — 1,517 runs, no hit —
while the same method matches the UI panel immediately.

### What else is solid

Sky and ground are flat colour bands, not artwork.

The list of objects to draw, and their positions, is readable at runtime. Their coordinates
run x 9..272, y 6..94.

### Not known

Three things, and all three block a working viewport:

- What computes the two per-row steps from an object's distance.
- Which asset a given viewport object's pixels come from.
- Which sprite a map cell selects, which is bytecode rather than data.

---

## 6. Text

    message.io   messaged.io   messagee.io   messagei.io    NPC and event text
    textin.io    textind.io    textine.io    textini.io     UI text
    sos.io       sosd.io       sose.io       sosi.io        asset filename tables

The suffix is the language:

    (none)  French
    d       German
    e       English
    i       Italian

French has no suffix because it is the fall-through case in the game's own selector, which
fits a French studio.

Strings are NUL-terminated. Each is preceded by a short record whose fields have not been
decoded.

---

## 7. The script VM

Ishar's game logic is bytecode stored inside the `.io` assets.

The bytecode's meaning is **not** in the assets. The four dispatch tables live in the
executable, so parsing `.io` files can never tell you what an opcode does.

### What is written in bytecode rather than data

- Which sprite a map cell draws.
- What the viewport composes for a given position.
- Encounter triggers.
- Quest and world state.

You can work around the small ones by hardcoding. You cannot work around the viewport.

### What is known about it

231 statement opcodes and 112 expression opcodes, including a complete operator set,
multi-dimensional arrays, and a jump-table switch.

The full tables are in `FORMATS.md` section 7.

---

## 8. How much of this is proven

Only **three** assets have been compared pixel for pixel against the running game:
`logo.io`, `buste.io` and `dead.io`.

The other 66 art assets decode through the same code path, which is itself verified, but
none of them has been individually checked.

Of the 2,370,078 bytes that decode out of the 98 assets, **47.9% sit in a structure that
has a name**. The rest is unexplained — `FILES.md` shows exactly where, per file.

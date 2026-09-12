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

Confirmed against the game's own video memory, opaque pixels only:

    asset      offset  size      mode  base  drawn at                    match
    frise.io   43176   64 x 12   0x12  192   x = 0,64,128,192,256 y=126   100%
    frise.io   42656   64 x 16   0x10  192   x = 64,128,192,256   y=184   100%
    buste.io    6986   64 x 36   0x10  208   (0, 147)                     100%
    frise.io   51456   32 x 126  0x10  208   (288, 0)                    85.8%
    frise.io   50712   16 x 8    0x10  208   (254, 175)                  95.0%
    frise.io   50568   16 x 8    0x10  192   (126, 175)                  83.9%

### The layout is a 64-pixel grid

The ACTION/ATTACK bar and the LIFE bar are each **one sprite drawn five times**, at
x = 0, 64, 128, 192, 256 — one column per party member.

You need one record and a stride of 64, not five records.

### The scores below 100% are all overdraw

The LIFE bar at x=0 scores 75.7% while the other four score 100%. The stored sprite is the
**empty** bar; character 1's is partly filled, and the fill is drawn on top.

The panel scores 85.8% because the region caption (rows 2-9), the compass needle (22-51)
and the DISK button (52-65) are composited over it.

So: draw the sprite, then draw the dynamic parts on top. Nothing is baked in.

### How a frame is put together

Everything is drawn into an off-screen buffer, then the whole buffer is copied to video
memory in one go.

    destination = buffer + y * 320 + x

### Not known

The grey medallion in an empty portrait slot is in **no asset**. Searched across all 106
files, as 8bpp and as 4bpp at every palette base that could hold it — while the same probe
found the portrait, both bars and the panel in the same frame.

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

**Two layers, not one.** A cell can be blocked by its terrain *or* by something standing on
it. The starting NPC walks around, and the cell he occupies refuses entry while he is on it
and allows it after he moves — with the grid byte unchanged throughout. So model occupancy
separately from terrain.

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

The current region is a byte the game keeps in its script variable area, and the ACTION
menu's ORIENTATION verb reports the region lying in the direction the party faces.

### Trap: region membership is code, not data

There is no table mapping a cell to a region. `gerdep.io`'s bytecode holds a list of
explicit conditions on the party's row and column:

    if (column < 46) && (region == 1)            a half-plane
    if (row == 25) && (column == 60) && ...      a single cell

So you either port those conditions or walk the map and record where the name changes.

### Trap: the world is gated

Walk far enough from the start and the game reloads the scene and puts the party back at
row 11, column 29.

Seen three times: twice heading north from `(13, 57)`, once heading west from `(39, 25)`.
The cells involved are ordinary `0x00` — this is a script gate, not terrain, so you cannot
predict it from the map.

The same reset happens if you attack a friendly NPC.

### What a cell value actually does

It is switched on. In `lacustre.io` the scene script reads the cell, stores it in a
variable, and dispatches:

    read    global[0x0080 + row,col]  ->  frame variable 33
    switch  on that variable, selector = value - 54, cases 0x36..0x39

Arms are shared — `0x37` and `0x38` go to the same place — and the first thing an arm does
is test the party's **facing**.

So a cell value has no meaning on its own. It is an index into a jump table written by hand
in each scene script, and you either port those switches or reimplement what they do.

### The party record is at least three bytes

    grid_end + 0   row
    grid_end + 1   column
    grid_end + 2   facing        reads 2 while ORIENTATION reports East

### Not known

Which sprite a cell value draws — the switch arms were not followed as far as a draw.

For the same reason, whether a cell blocks movement is not a function of its value alone.
The same value blocks in one place and not another.


---

## 5. The 3D viewport

This is the least understood part of the game.

### The renderer does not scale

The viewport has its own drawing routines, separate from the ones that draw the UI. They
copy a sprite into the frame buffer one row at a time.

Measured live: the destination pointer advances **exactly 320 per row** and the source
pointer **exactly one source row**. The copy is 1:1. Nothing is stretched, squashed or
sheared.

Two of the routines' per-row constants look like they might encode a projection. They do
not — one is `320 + pixels drawn` and the other is `source stride − bytes consumed`. Both
are simply "move to the next row".

### So where does distance come from?

From **which sprite is drawn**, not from how it is drawn.

`arbre.io` holds fifteen sprites in a graded ladder of sizes:

    16x15   16x27   16x43   16x47   16x65
    32x25   32x40   32x62   32x71   32x101
    48x38   64x67   64x72   80x128  144x83

A tree twice as close is a different, larger sprite — not the same sprite scaled up.

Two rungs were caught on screen **in the same frame** at different heights — @25490 (16x27)
at (247,61) and @25714 (16x15) at (256,66) — which is the ladder in use. Which rung goes
with which distance is still open.

### Characters are drawn from stacked parts

Not one sprite per distance. Adjacent to the starting NPC, two `bormin.io` sprites are on
screen:

    bormin.io @3714   48 x 31   at (103, 60)   the upper half   100%  vs VRAM
    bormin.io @2770   48 x 39   at (104, 91)   the lower half   92.8%

Contiguous, one pixel apart in x, together 48 x 70. So for a character you need, per range,
**the set of parts and their relative offsets** — here upper over lower at dx +1, dy +31.

At three cells away the same NPC is a single 16x29 sprite with nothing stacked under it, so
the number of parts changes with range too.

For a rewrite this is far less work than a projection: pick the sprite, blit it 1:1 at its
position. No perspective maths.

### Objects are clipped at the viewport edge

A draw can be narrower than its source. Both widths seen so far, 17 px and 32 px, came from
the same 32-pixel-wide sprite — the narrow one was clipped where it ran off the edge.

### Sky and ground are tiled sprites

Both come from `fond.io`.

    fond.io @2750   64 x 85   the sky,    drawn at (96, 0)
    fond.io @1366   64 x 43   the ground, tiled across the viewport at y = 83

The ground is **one sprite repeated every 64 pixels**, clipped at both edges. In the frame
measured, its run started at x = -17 — that offset is what a rewrite needs to make the
ground appear to move.

### Which assets the view is built from

    fond.io      the backdrop
    plaine.io    outdoor scenery — the bushes and trees — at palette base 16
    arbre.io     fifteen graded tree sizes — never yet seen on screen

Confirmed by matching stored sprite bytes against video memory:

    plaine.io  @24720  48x58  base 16  seen at ( 98, 68)   100%
    plaine.io  @26120  48x67  base 16  seen at (146, 59)   100%
    plaine.io  @24440  16x34  base 16  seen at ( 82, 93)   100%

### Three routines draw the viewport

    a rectangle fill        sky and ground bands
    an opaque expander      no transparency test
    a masked expander       skips nibble 0

All three write the same off-screen buffer. Which one draws a given thing was settled by
watching writes to a single pixel, with a control breakpoint on memory the program never
touches — without the control, an idle-loop address swamps the result.

### Reading a frame

Because the blit is 1:1, a sprite on screen matches its stored bytes **exactly**. So you
can check your renderer against the real game: take a sprite's longest opaque run, find it
in a screenshot's indices, then compare the whole sprite.

`tools/onscreen.py` does this across all 98 assets and lists what is on screen and where.

Two things make a naive version of this fail. Masked sprites have background showing
through their holes, so only *opaque* runs can be matched; and a whole asset never matches,
only individual sprites.

### What is readable at runtime

The list of objects to draw and their positions. Coordinates run x 9..272, y 6..94.

### Horizontal placement, as far as it is measured

An object slides sideways as the party moves laterally, by an amount that depends on its
distance:

    3 cells away    88 pixels per lateral cell    (measured on the NPC)
    ~7 cells away   38 pixels per lateral cell    (measured on a tree)

Consistent with `pixels per cell = 264 / distance`, though that constant rests on two
points and the tree's distance was inferred from its own slope.

**Absolute position needs one more thing.** A sprite's origin is not the object's centre —
each sprite carries an anchor offset nobody has measured — so two frames of the same object
give you the slope, and one frame does not give you the position.

### How to place objects, given that

Use `pixels per lateral cell = 264 / distance` and calibrate the rest against a screenshot.

That is a working recipe, not a derivation. Four attempts to derive it failed, each for a
different reason: sprites do not identify an object (two trees share one), objects cannot be
tracked (NPCs walk, trees are alike), positions are not stored in memory, and the draw order
is not reproducible under a breakpoint. If you need better than calibration, the route is a
cycle-accurate trace rather than a breakpoint, so that a frame is a frame.

### Not known

- Which sprite of the ladder is chosen at which distance, and how position is derived.
- Which sprite a map cell selects — that is bytecode, not data.
- **Where characters come from.** The NPC standing near the start is in **no asset** — every
  sprite of all 98 files at every palette base was checked, while seven other things in the
  same frame matched at 100%. Scenery is findable; people are not, yet.



---

## 6. Text

### The font is in main.io

Text is drawn glyph by glyph from 16x9 sprites in `main.io`, at **7-pixel spacing**.

Confirmed offsets: @23272, @23662, @23740, @23896, @24286, @24598 — six of the glyphs that
spell the region caption.

### The strings

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

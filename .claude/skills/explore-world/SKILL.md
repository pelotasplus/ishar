---
name: explore-world
description: Use when a question needs the party somewhere specific in Ishar's world - reading its map cell, its region, walking it to a cell, or deciding whether a refused move is terrain or a gate. Carries the addresses, the tools, and the three ways the game looks broken when it is not.
---

# Moving and reading the party

The world is six `cont*.fic` grids, **90 x 54 bytes, one per cell, indexed `row * 90 + col`**,
loaded verbatim (FORMATS 3.12). One is resident at a time.

    tools/mappos.py            find the resident grid and the party, from scratch
    tools/region.py            the party's cell and region, by name
    tools/region.py Up 20      walk 20 steps, printing the region at each
    tools/walkto.py ROW COL    drive the party there, learning blocked cells

## Where the state lives

Everything hangs off the VM's global base, the far pointer at `ss:[0bf6]`
(`126b:02a0` = linear `0x12950`, the same across restarts so far):

| global offset | field |
|---|---|
| `+0x0080` | the 90x54 grid, `cont*.fic` verbatim |
| `+0x137C` | party row |
| `+0x137D` | party column |
| `+0x3EAC` | region id, 0..20 into the 21 names in FINDINGS 4.19b |

The row/col pair sits at `grid_end` because it is the next field of the same structure,
not by luck. Do not hard-code `ss:[0x644c]` — `tools/mappos.py` finds it.

## Movement

**Absolute, not relative.** Up/Down change the row, Left/Right the column, and the party
never turns. There *is* a facing — ACTION → ORIENTATION reports the region lying in it —
but nothing found yet sets it.

A move that leaves row/col unchanged was **refused**, and that is the only reliable signal
that a cell is blocked. `0xCC`/`0xCD` (water) and `0xE6` refuse; so does `0x0A` in one place
and not another, so **blocking is not a function of the cell value** — a script decides.

## Three ways this looks broken when it is not

- **The world is gated.** Walk far enough from the start and the scene reloads and the
  party is returned to its starting cell — the same outcome as the murder consequence.
  Seen at `(13,57)` twice and from `(39,25)`. Ordinary `0x00` cells. Budget for it: no
  wander-based experiment has ever got more than a dozen cells out.
- **A modal verb freezes movement.** PICK LOCK or ATTACK armed but not yet aimed blocks the
  arrow keys entirely. Check the pointer's shape before concluding the party is stuck.
- **Writing row/col does not teleport.** Those bytes are a copy the engine updates after a
  successful move and never reads back. The write sticks, the view does not rebuild, and
  the game carries on from where it really was. Walk; do not poke.

## Reading the region name

`ss:[0x0902]` holds it *at rest* and is a **shared string workspace** — during a scene load
it carries `main.io`, `EN1.FIC`, `foret.io`; during dialogue, message text. A probe that
scrapes it must check the value spells one of the 21 names. Prefer the region id at
`+0x3EAC`, which is the variable the game itself switches on.

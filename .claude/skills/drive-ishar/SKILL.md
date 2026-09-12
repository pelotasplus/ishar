---
name: drive-ishar
description: Use when Ishar needs to be running under Spice86 - to reach a screen, read memory, set a breakpoint, or capture a reference screenshot. Carries the harness commands, the boot recipe, and the traps that cost whole sessions.
---

# Driving Ishar under Spice86

`run.sh` is for *playing* the game. `tools/ish` is for *measuring* it: fixed clock,
sync rendering, dummy audio, no CFG reload, so cycle counts mean the same thing twice.

    tools/ish start [--gdb] [--pause] [--window] [--audio on|off|none]
    tools/ish boot                 drive to gameplay and prove it got there
    tools/ish status | log [N] | stop [--all]
    tools/ish regs | mem SEG:OFF LEN | dis SEG:OFF [N] | poke SEG:OFF HEX
    tools/ish bp ADDR [--type T] [--cond C] | bps | clearbp
    tools/ish go | pause | step [N] | run-until SEG:OFF | run-for CYCLES
    tools/ish keys K [K...] | shot NAME | wait CAPTURE | funcs [LIMIT]

`--pause` halts at the program entry so a tracer can arm breakpoints before the game
opens a single file. `--gdb` adds the stub (see `trace-dos-calls`). `shot NAME` writes
straight into `captures/NAME.png`, which is where reference images belong.

## Getting into the game

`tools/ish boot` sends Kp1 / Escape / Space until the party panel is on screen, then
stops. It checks by comparing rows 260-399 against `captures/game-party-panel.png`:
that strip is pixel-identical across different locations (measured: 0 of 89,600 pixels
differ), so it cannot be confused with the intro. Typically ~11 nudges, ~45s.

Kp1, not top-row 1: the shipped scancode table gives `&` for the top row (FINDINGS
§2.1). `run.sh` patches that for play; a measurement run should stay as the game
shipped.

## Traps

- **Keys need down *and* up.** `send_keyboard_key` twice, `isPressed` true then false.
- **"Enqueued while paused" does not mean paused.** To know if the machine runs, sample
  `read_cpu_state` twice and compare `Cycles`.
- **A still screen is not a hung screen — and not a slow one either.** `tools/ish status`
  first, story never: it reads the log and says `faulted` in a second. The sentence that
  used to sit here, "a black screen is usually the intro, which runs for minutes", was
  wrong and got offered to the user as the explanation for a dead machine. The intro is
  about three screens.
- **`list_functions` needs an explicit limit** or it returns an error; it also defaults
  to 100, which looks like a complete answer.
- **Emulators pile up.** `ish stop --all` kills every one it can find; `start` reaps
  first. Eleven were once running at once. If things feel slow, count them.
- **The game crashes** in the timer interrupt after a couple of minutes, and there is a
  second garbage-execution fault (FINDINGS §5.0, §5.1). `ish status` says `faulted`;
  check it before trusting a late reading.
- **`send_mouse_move` takes normalised 0.0-1.0 coordinates**, not pixels. Pixels answer
  `Mouse moved to (1.000, 1.000)` — clamped to the corner, so nothing fires, and it
  reports success either way. Use `tools/mclick X Y --click`.

## Driving the game's UI

The mouse works (T29c3 wired the device to the input hub instead of the GUI — two lines
in `Spice86DependencyInjection.cs`, committed there, not pushed). Everything below the
viewport is pointer-driven.

    tools/mclick 0.055 0.663 --click     # ACTION on character 1
    tools/mclick 0.133 0.663 --click     # ATTACK on character 1

- **Verbs are two-step and modal.** ATTACK and PICK LOCK arm the pointer — its shape
  changes — and then need a *target* click. Until one is used or cancelled, **the arrow
  keys do not move the party**, which reads exactly like the game having frozen.
- **Clicking a menu entry once highlights it; twice commits it.**
- **Clicking a portrait opens that character's inventory, and nothing found closes it.**
  The panel swaps the face for a slot grid, and while it is up the arrow keys do not move
  the party -- which reads as the game having frozen, and `tools/walkto.py` reports every
  direction refused. Escape, a second click on the portrait (that click lands on an
  inventory slot instead), a right click, and the red square in the panel's corner were all
  tried and none closed it. Recovering cost a restart. Do not open it unless the inventory
  is the thing being measured (`captures/t60-inventory.png`).
- **Do not click destructive verbs while sweeping a menu.** A KILL click during an
  exploratory pass left the game in a state that could not be reasoned about, and there
  were then two candidate causes for the damage instead of none.

## Screen comparisons

`tools/png.py` reads and writes PNG with no third-party library, because the pixel
comparison is what M3 and M4 accept as proof. `ish wait NAME [--region x,y,w,h]` blocks
until the screen matches a capture. A size mismatch means a different video mode, not a
mismatch: the game is 720x400 text during boot and 640x400 after.

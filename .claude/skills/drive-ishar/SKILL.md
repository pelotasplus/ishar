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
- **A black screen is usually the intro**, which runs for minutes. Check cycles before
  calling anything hung.
- **`list_functions` needs an explicit limit** or it returns an error; it also defaults
  to 100, which looks like a complete answer.
- **Emulators pile up.** `ish stop --all` kills every one it can find; `start` reaps
  first. Eleven were once running at once. If things feel slow, count them.
- **The game crashes** in the timer interrupt after a couple of minutes, and there is a
  second garbage-execution fault (FINDINGS §5.0, §5.1). `ish status` says `faulted`;
  check it before trusting a late reading.
- **The mouse cannot be driven** — `send_mouse_move` does not move the in-game cursor.

## Screen comparisons

`tools/png.py` reads and writes PNG with no third-party library, because the pixel
comparison is what M3 and M4 accept as proof. `ish wait NAME [--region x,y,w,h]` blocks
until the screen matches a capture. A size mismatch means a different video mode, not a
mismatch: the game is 720x400 text during boot and 640x400 after.

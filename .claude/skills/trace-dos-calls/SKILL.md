---
name: trace-dos-calls
description: Use when you need to know which files the game opens or reads, and which routine wanted them. Carries the MCP-arms-GDB-delivers design, why neither half works alone, and how to name the caller.
---

# Tracing the game's DOS calls

    tools/ish start --gdb --pause
    tools/gdbtrace.py --stop-after logo.io          # or --seconds 60, --opens-only

Roughly 18 file calls from launch to the Silmarils logo, in about 8 seconds.

## Why it is built this way

Neither half works alone, and both failures are silent:

- **MCP** takes a conditional breakpoint that filters properly, but nothing tells the
  client when it fires. `tools/trace-io.py` polls `read_cpu_state`, and every poll
  pauses the emulator: the traced boot runs ~10x slower than real time.
- **The GDB stub** pushes a stop packet when a breakpoint fires, so the client blocks on
  a socket and the game runs full speed — but a condition on a `Z` packet is accepted
  with `OK` and then ignored, so you stop on all ~500k INT 21h calls.

So: arm the conditional breakpoint over MCP, wait for stops over GDB. Spice86 notifies
the GDB client on *any* pause, which is what makes the pairing work. Measured on the
same milestone: ~420s polling, 7.7s this way.

## Traps

- **A stop is not evidence of a breakpoint.** Screenshots, MCP calls and the UI all
  pause the machine and all produce stop packets. Check `ip` against the breakpoint
  address before reading anything into the registers.
- **Do not wake the tracer on a timer.** Keys, screenshots, anything periodic costs a
  `continue`, which is itself a pause/resume. Ticking every 2s made a 3.5s startup take
  27s; every 0.4s made it 61s. Keys go in a separate process (`tools/nudge.py`).
- **The INT frame names the wrapper, not the caller.** `SS:SP` holds the return address
  inside `dos_read_asset`. The routine that wanted the file is one word further up, at
  `SS:SP+6` — or `SS:SP+8` for opens, because `dos_open_asset` pushes AX first. Without
  this every caller reads as the wrapper and names nothing.
- **A GDB error reply is `E` plus exactly two hex digits.** Memory whose first byte is
  `0xEB` comes back as `EB1F7D01`; `startswith("E")` throws away a good read.
- **The `c` ack and a pushed stop share one stream** and can arrive in either order, so
  a register read comes back as `'OK'` unless acks are skipped and stops queued.

## What it produces

`.ish/io-trace-gdb.json`, plus a table of op, file, buffer, length, and both callers.
Feed the outer callers into `ishar.chani` — that is the point of the exercise; the
behaviour without the addresses is a story nobody can build on.

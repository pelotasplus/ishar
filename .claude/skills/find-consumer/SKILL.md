---
name: find-consumer
description: Use when the question is who touches a value - which code reads or writes an address, or which of the game's scripts is running during an action. Carries the two instruments, the phantom stops that make both lie, and the filters that make them usable.
---

# Finding out who touches something

Two instruments, for two different questions.

## Which code reads or writes an address

Arm a memory breakpoint over MCP, take the stop over GDB (`trace-dos-calls` explains why
the hybrid). `add_breakpoint` accepts `MEMORY_READ`, `MEMORY_WRITE` and `MEMORY_ACCESS`.

    tools/t11g3d-reader.py ROW COL          who reads one map cell
    tools/t11g3d-site.py ROW COL A B SECS   the same, driven, with the script PC

**A memory breakpoint has no IP to check against**, so the guard that works for execution
breakpoints — compare `r["ip"]` unmasked against the armed linear address — does not exist
here. What replaces it:

- **Filter the known phantoms.** `seg_0000:3d64` is `wait_loop`, the idle spin, and *any*
  pause reports it: an MCP call, a screenshot, the UI. `seg_0000:93b5` is `adlib_sequencer`,
  whose stream pointer parks in memory overlapping the loaded map and reads a zero there.
  Both were briefly read as real consumers.
- **A run that produces only phantoms is not a result.** Two such runs were nearly written
  up as "nobody reads this". Discard them and re-aim.
- **The reported IP is the *return* point**, not the reading instruction. For a VM read it
  lands on `seg_0000:7153`, the expression-sequence loop, with the handler that did the read
  already returned. To identify the opcode, read the script bytes just before `DS:SI`.
- **Aim at something the game will actually touch.** Watching a map cell the party is
  nowhere near gives zero reads and looks like a negative result.

For a `MEMORY_WRITE`, read the watched bytes at the stop and check they hold what you think
was just written. Once, 4 stops agreed and 5,868 did not, and a whole finding rested on it.

## Which script is running

`read_cpu_state` polls at ~3,550 samples/s without disturbing the game, against ~2.6 useful
stops/s for a breakpoint drowning in ~340 background stops/s. **Poll, do not break.**

    tools/t44-when.py LABEL SECONDS "shell command to drive the game"

`SI` is the script's program counter **only while the CPU is inside `vm_run`'s fetch loop**,
so samples are kept only when `CS == load` and `IP` is in `0x26eb..0x26f8`. Without that
filter the poll attributes any moment `SI` happens to point into a buffer, which is not
execution. Matching 64 bytes at `DS:SI` against every decoded asset names the script.

Use it to answer "what runs when X happens" by differencing windows: an idle window and an
action window of equal length, keyed on `(segment, offset)` — keying on offset alone once
mislabelled `seg_0e97:038b` as `seg_0000:038b` throughout a task.

## The negative result is a claim about the instrument

Before reporting that nothing reads an address or no script runs, arm the same probe on
something known to fire — `seg_0000:93a6` runs thousands of times a second — and check it
reports hits. Five zero-hit runs in T27 were the instrument, not the game.

---
name: drive-ishar
description: Use when Ishar needs to be running under Spice86 - to reach a screen, read its memory, or capture a reference screenshot. Carries the boot sequence, the MCP call shape, and the traps that waste a session.
---

# Driving Ishar under Spice86

## Start it

    ./run.sh --HeadlessMode Minimal      # prints the ports it picked
    ./run.sh                             # visible window, for watching

`run.sh` boots the *unpacked* binary (rebuilding it if stale) and picks free ports,
printing them: `GDB port N, HTTP API port N, MCP port N`.
Read the MCP port from that line — do not assume 8091. It also patches the keyboard
table so top-row digits work (`NO_REMAP=1` to skip), and `AUDIO=off|none` silences or
removes the sound cards.

## Talk to it

One JSON-RPC POST per call; the reply is an SSE `data:` line:

    curl -s -H 'Content-Type: application/json' \
         -H 'Accept: application/json, text/event-stream' \
         -X POST "http://localhost:$PORT/mcp" \
         -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
              "params":{"name":"read_cpu_state","arguments":{}}}' \
      | grep '^data: ' | sed 's/^data: //'

Useful tools: `read_cpu_state`, `read_memory` (segment/offset/length, max 4096),
`write_memory`, `search_memory`, `read_disassembly` (segment/offset/instructionCount),
`add_breakpoint` (linear address + `CPU_EXECUTION_ADDRESS` | `MEMORY_WRITE` | ...),
`clear_breakpoints`, `resume_emulator`, `pause_emulator`, `step`, `screenshot`,
`send_keyboard_key`, `read_dos_program_state`, `list_functions`, `read_cfg_cpu_graph`.

## Boot to gameplay

About 40 s to the language menu, then:

| step | keys | wait |
|---|---|---|
| language menu | `D1` (or `Kp1`) | ~4 s |
| credits | `Escape` | ~30 s |
| intro | `Escape`, `Space` | ~20 s |
| gameplay | — | — |

Left alone, the intro loops back to the language menu. Confirm each step with a
`screenshot` rather than assuming the key landed.

## Traps

- **Keys need down and up.** `send_keyboard_key` twice: `isPressed: true`, then
  `false`. One call is half a keypress.
- **"Enqueued while paused" does not mean paused.** To know if the machine runs,
  sample `read_cpu_state` twice and compare `Cycles`.
- **A black screen is usually the intro**, which is minutes long. Check cycles before
  calling anything hung.
- **Killing it.** `timeout`/`pkill -f run.sh` kill the `dotnet run` wrapper and leave
  the emulator holding the ports. Use `pkill -f "McpHttpPort <port>"`, then check `ps`.
- **Screenshots land in a temp dir** that gets cleared. Copy to `captures/` with a real
  name in the same step.
- **The game crashes in the timer interrupt** after a couple of minutes
  (`FINDINGS.md` §5.1). Grep the log for `Emulation failed` before trusting a late
  reading.
- **The mouse cannot be driven yet** — `send_mouse_move` does not move the in-game
  cursor. Keyboard only.

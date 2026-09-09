#!/usr/bin/env bash
#
# Run Ishar: Legend of the Fortress under Spice86.
#
# Defaults to the UNPACKED binary: the shipped start.exe is LZEXE-packed behind a
# self-extracting stub, so a debugger attached to it sees the unpacker, not the
# game. tools/unpack.py rebuilds start-unpacked.exe, and this regenerates it when
# it is missing or older than the original. It lives beside the game's own files,
# because --CDrive makes that folder C: -- but it is derived, and gitignored.
#
#   ./run.sh                        Avalonia window
#   ./run.sh --HeadlessMode Minimal no window
#   EXE=.../start.exe ./run.sh      the shipped packed binary, stub and all
#   AUDIO=off ./run.sh              emulate the sound cards, but stay silent
#   AUDIO=none ./run.sh             no Sound Blaster and no OPL at all
#   RELOAD_CFG=on ./run.sh          reuse the CFG graph dumped by earlier runs
#
# The GDB / HTTP API / MCP ports are picked free at startup, so several
# instances can run at once. Pin one with GDB_PORT / HTTP_PORT / MCP_PORT,
# or set it to 0 to turn that server off. Anything else goes to Spice86.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPICE86_DIR="${SPICE86_DIR:-$SCRIPT_DIR/../Spice86}"
GAME_DIR="$SCRIPT_DIR/ishar_legend_of_the_fortress_DOSGamer.com"
PACKED="$GAME_DIR/start.exe"
UNPACKED="$GAME_DIR/start-unpacked.exe"

if [ -z "${EXE:-}" ]; then
  if [ ! -f "$UNPACKED" ] || [ "$PACKED" -nt "$UNPACKED" ]; then
    python3 "$SCRIPT_DIR/tools/unpack.py" >&2
  fi
  EXE="$UNPACKED"
fi

# Spice86 reloads the CFG graph it dumped on a previous run by default. This
# game relocates its code between runs, so that cross-run state is a variable
# we do not want while chasing crashes -- off unless asked for.
if [ "${RELOAD_CFG:-off}" = "on" ]; then
  RELOAD_CFG_ARG=true
else
  RELOAD_CFG_ARG=false
fi

case "${AUDIO:-on}" in
  on)   AUDIO_ARGS=() ;;
  off)  AUDIO_ARGS=(--AudioEngine Dummy) ;;
  none) AUDIO_ARGS=(--AudioEngine Dummy --SbType None --OplMode None) ;;
  *)    echo "AUDIO must be on, off or none (got '$AUDIO')" >&2; exit 1 ;;
esac

# First free port at or above $1.
free_port() {
  local port=$1
  while [ "$port" -lt $(($1 + 100)) ]; do
    if [ -z "$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null)" ]; then
      echo "$port"
      return
    fi
    port=$((port + 1))
  done
  echo "No free port in $1..$(($1 + 99))" >&2
  exit 1
}

# A pinned port is used as given, but checked -- Spice86 dies with a Kestrel
# stack trace rather than a useful message when one is already taken.
check_pinned() {
  if [ "$2" != 0 ] && [ -n "$(lsof -nP -iTCP:"$2" -sTCP:LISTEN -t 2>/dev/null)" ]; then
    echo "$1 $2 is already in use (another emulator still running?)" >&2
    exit 1
  fi
}

if [ -n "${GDB_PORT:-}" ]; then check_pinned GDB_PORT "$GDB_PORT"; else GDB_PORT=$(free_port 10010); fi
if [ -n "${HTTP_PORT:-}" ]; then check_pinned HTTP_PORT "$HTTP_PORT"; else HTTP_PORT=$(free_port 20010); fi
if [ -n "${MCP_PORT:-}" ]; then check_pinned MCP_PORT "$MCP_PORT"; else MCP_PORT=$(free_port 8091); fi

if [ ! -d "$SPICE86_DIR/src/Spice86" ]; then
  echo "Spice86 not found at $SPICE86_DIR (override with SPICE86_DIR=...)" >&2
  exit 1
fi

if [ ! -f "$EXE" ]; then
  echo "Game executable not found at $EXE" >&2
  exit 1
fi

echo "GDB port $GDB_PORT, HTTP API port $HTTP_PORT, MCP port $MCP_PORT" >&2

# The game's own INT 9 table gives the top number row French characters, so
# its 1-4 menus only answer to the keypad. Patch it once the game is up.
if [ -z "${NO_REMAP:-}" ] && [ "$MCP_PORT" != 0 ]; then
  MCP_PORT="$MCP_PORT" "$SCRIPT_DIR/remap-digits.sh" &
fi

# --CDrive is what the game sees as C:, and it is where it looks for its
# .io / .fic data files and start.stp.
dotnet run --project "$SPICE86_DIR/src/Spice86" -- \
  --Exe "$EXE" \
  --CDrive "$GAME_DIR" \
  --GdbPort "$GDB_PORT" \
  --HttpApiPort "$HTTP_PORT" \
  --McpHttpPort "$MCP_PORT" \
  --ReloadCfgGraph "$RELOAD_CFG_ARG" \
  "${AUDIO_ARGS[@]}" \
  "$@"

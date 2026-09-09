#!/usr/bin/env bash
#
# Log every write to the INT 8 (timer) vector at 0000:0020.
#
# Both crashes so far ended with the timer interrupt landing on code that was
# no longer a handler. This records who installs the vector and when, so the
# last install before a crash can be compared against what is at that address
# when it blows up. Each hit pauses the emulator briefly, then resumes.
#
#   ./watch-int8.sh              log to stdout until interrupted
set -e

MCP_PORT="${MCP_PORT:-$(ps -eo command= | grep "[i]shar_legend" | tr ' ' '\n' | grep -A1 -x -- --McpHttpPort | tail -1)}"
if [ -z "$MCP_PORT" ]; then
  echo "No running Ishar emulator found (start it with ./run.sh), or set MCP_PORT=..." >&2
  exit 1
fi

mcp() {
  curl -s --max-time 10 -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
    -X POST "http://localhost:$MCP_PORT/mcp" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}" \
    | grep '^data: ' | sed 's/^data: //'
}

mcp clear_breakpoints '{}' > /dev/null
for addr in 32 33 34 35; do   # 0000:0020..0023, the four vector bytes
  mcp add_breakpoint "{\"address\":$addr,\"type\":\"MEMORY_WRITE\",\"condition\":null}" > /dev/null
done
mcp resume_emulator '{}' > /dev/null
echo "watching INT 8 vector on port $MCP_PORT (ctrl-c to stop)" >&2

trap 'mcp clear_breakpoints "{}" > /dev/null; mcp resume_emulator "{}" > /dev/null; exit 0' INT TERM

while true; do
  state=$(mcp read_cpu_state '{}' | python3 -c "
import sys, json
s = json.load(sys.stdin)['result']['structuredContent']
print('%04X:%04X' % (s['CS'], s['IP']), s['Cycles'])" 2>/dev/null) || { sleep 1; continue; }
  cycles=${state#* }
  if [ "$cycles" = "$last_cycles" ]; then
    vec=$(mcp read_memory '{"segment":0,"offset":32,"length":4}' | python3 -c "
import sys, json
b = bytes.fromhex(json.load(sys.stdin)['result']['structuredContent']['Data'])
print('%04X:%04X' % (int.from_bytes(b[2:4],'little'), int.from_bytes(b[0:2],'little')))" 2>/dev/null)
    printf '%s  writer at %s  INT 8 -> %s\n' "$(date +%H:%M:%S)" "${state% *}" "$vec"
    mcp resume_emulator '{}' > /dev/null
  fi
  last_cycles=$cycles
  sleep 0.3
done

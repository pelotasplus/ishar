#!/usr/bin/env bash
#
# Make the top-row number keys work in Ishar.
#
# The game hooks INT 9 and translates scancodes through its own table. Its
# letter rows are QWERTY, but the number row is French: scancode 0x02 ('1')
# yields '&', 0x03 yields 'e-acute', and so on -- so menus that ask for 1-4
# only answer to the numeric keypad. This rewrites those ten table entries
# to '1'..'0' in the running emulator's memory.
#
# run.sh does this for you; run it by hand if you started Spice86 some other
# way. WAIT_SECONDS controls how long it waits for the table to show up.
set -e

MCP_PORT="${MCP_PORT:-$(ps -eo command= | grep "[i]shar_legend" | tr ' ' '\n' | grep -A1 -x -- --McpHttpPort | tail -1)}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"

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

# The table's first entries, scancode 0x01 onwards: Esc, then the French
# number row. Distinctive enough to find the table wherever DOS loaded it.
SIG="1B2682222728608A218785292D080971"

find_table() {
  mcp search_memory "{\"pattern\":\"$SIG\",\"startSegment\":0,\"startOffset\":0,\"length\":1048576,\"limit\":4}" \
    | python3 -c "
import sys, json
try:
    hits = json.load(sys.stdin)['result']['structuredContent'].get('Matches') or []
except Exception:
    sys.exit(1)
if not hits:
    sys.exit(1)
print(hits[0]['Segment'], hits[0]['Offset'])"
}

for _ in $(seq "$WAIT_SECONDS"); do
  if read -r SEG OFF <<<"$(find_table)" && [ -n "$SEG" ]; then
    # Entry N is scancode N+1, so the number row starts one byte in.
    mcp write_memory "{\"segment\":$SEG,\"offset\":$((OFF + 1)),\"data\":\"31323334353637383930\"}" > /dev/null
    printf 'Key table patched at %04X:%04X - top-row 1..0 now work\n' "$SEG" "$((OFF + 1))" >&2
    exit 0
  fi
  sleep 1
done

echo "Key table not found after ${WAIT_SECONDS}s; top-row digits still map to French characters" >&2
exit 1

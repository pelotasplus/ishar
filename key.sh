#!/usr/bin/env bash
#
# Send a keypress to the running Ishar emulator over Spice86's MCP port.
#
#   ./key.sh Kp1        keypad 1 (the game's menus want the keypad, not the top row)
#   ./key.sh Enter Kp2  several keys in order
#
# Key names are PcKeyboardKey values: A-Z, D0-D9, Kp0-Kp9, Enter, Escape,
# Space, Up/Down/Left/Right, F1-F12, LeftShift, LeftCtrl, LeftAlt...
set -e

MCP_PORT="${MCP_PORT:-$(ps -eo command= | grep "[i]shar_legend" | tr ' ' '\n' | grep -A1 -x -- --McpHttpPort | tail -1)}"
if [ -z "$MCP_PORT" ]; then
  echo "No running Ishar emulator found (start it with ./run.sh), or set MCP_PORT=..." >&2
  exit 1
fi

call() {
  curl -s -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
    -X POST "http://localhost:$MCP_PORT/mcp" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"send_keyboard_key\",\"arguments\":{\"key\":\"$1\",\"isPressed\":$2}}}" \
    > /dev/null
}

for key in "$@"; do
  call "$key" true
  sleep 0.1
  call "$key" false
  sleep 0.2
  echo "sent $key" >&2
done

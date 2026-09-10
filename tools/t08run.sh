#!/bin/bash
# Retry a language trace until one survives the ~45s intro fault (FINDINGS 5.3).
LANG_KEY="$1"; SECS="${2:-300}"; TRIES="${3:-6}"
cd "$(dirname "$0")/.."
for i in $(seq 1 "$TRIES"); do
  tools/ish stop --all >/dev/null 2>&1
  tools/ish start --gdb --pause --audio none >/dev/null 2>&1
  echo "--- $LANG_KEY attempt $i ---"
  tools/gdbtrace.py --drive "$LANG_KEY" --seconds "$SECS" > ".ish/t08-$LANG_KEY.txt" 2>&1
  if grep -q FAULTED ".ish/t08-$LANG_KEY.txt"; then
    echo "faulted: $(grep -o 'FAULTED.*' ".ish/t08-$LANG_KEY.txt" | head -1)"
    continue
  fi
  # "did not fault" is not "reached gameplay" -- a french run survived its whole
  # budget stuck on the menu and was reported as success. plaine.IO is the first
  # outdoor asset, so it only appears once the game proper is running.
  if ! grep -q 'plaine.IO' ".ish/t08-$LANG_KEY.txt"; then
    echo "survived but never reached gameplay ($(grep -c ' open ' ".ish/t08-$LANG_KEY.txt") opens)"
    continue
  fi
  cp .ish/io-trace-gdb.json ".ish/t08-$LANG_KEY.json"
  echo "reached gameplay; $(grep -c ' open ' ".ish/t08-$LANG_KEY.txt") opens"
  exit 0
done
echo "all $TRIES attempts faulted"
exit 1

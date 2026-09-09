#!/usr/bin/env bash
#
# Regenerate the listing from the annotation database, and report coverage.
#
#   tools/disasm.sh [out]        default: ishar-listing.txt (derived, not committed)
#
# The listing is OUTPUT. Never edit it -- edit ishar.chani and rerun.
#
# The disassembler is madmoose's chani-rs. It is NOT vendored and must not be:
# it carries no licence, so it is a local instrument like a debugger, never a
# build dependency. Point CHANI_HOME at a checkout.
#
#   cd $CHANI_HOME && cargo build --release -p chani_disasm --bins
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHANI_HOME="${CHANI_HOME:-$HOME/Workspace/pelotasplus/dune/chani-rs}"
DISASM="$CHANI_HOME/target/release/disasm"
OUT="${1:-$HERE/ishar-listing.txt}"

[[ -x "$DISASM" ]] || {
    echo "error: no disasm at $DISASM" >&2
    echo "       set CHANI_HOME, or build with:" >&2
    echo "       cd \$CHANI_HOME && cargo build --release -p chani_disasm --bins" >&2
    exit 1
}
# ishar.chani describes the UNPACKED image; the shipped start.exe is packed.
[[ -f "$HERE/ishar_legend_of_the_fortress_DOSGamer.com/start-unpacked.exe" ]] || python3 "$HERE/tools/unpack.py" >&2

cd "$HERE"
"$DISASM" ishar.chani > "$OUT"
echo "$OUT"
python3 tools/cover.py "$OUT"

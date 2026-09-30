#!/bin/bash
# [V536] Produce the G-T5-RESTORE golden vector for THIS release with the incantation in
# tests/restore_check.sh (extracted from that file so the two cannot drift).  Run it ONCE per release,
# with the release encoder, and commit the vector; never run it to make a failing gate pass.
set -u
D="$(cd "$(dirname "$0")/.." && pwd)"; TD="${TMPDIR:-/tmp}"; CELL="$TD/omc_restore_cell_$$.yuv"; trap 'rm -f "$CELL"' EXIT
OUT="$D/delivery/conformance/vectors/c536_policy_restore_rail.omc"
python3 "$D/tests/mkrail.py" "$CELL" 1280 720 10 6 >/dev/null 2>&1 || { echo "mkref FAIL: cell"; exit 1; }
INC=$(sed -n '/^OMC_GM_PLANRESET=0/,/^"\$D\/omc_enc"/p' "$D/tests/restore_check.sh" | grep -v omc_enc | tr -d '\\' | tr '\n' ' ')
[ -n "$INC" ] || { echo "mkref FAIL: could not extract the incantation"; exit 1; }
env $INC "$D/omc_enc" -i "$CELL" -o "$OUT" -w 1280 -h 720 --fmt 422 --depth 10 --bpp 0.5 -n 6 >/dev/null 2>&1 || { echo "mkref FAIL: encode"; exit 1; }
sha256sum "$OUT" | tee "$D/delivery/conformance/expected/c536_policy_restore_rail.stream.sha256"
echo "golden vector written: $OUT ($(stat -c%s "$OUT") bytes, minor $(grep -oE '#define OMC_MINOR_T5 [0-9]+' "$D/include/omc1.h" | grep -oE '[0-9]+$'))"

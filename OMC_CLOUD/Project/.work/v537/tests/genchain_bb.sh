#!/bin/bash
# genchain_bb.sh - T5 generation-exactness chain test over PURE BASEBAND
# interchange: every generation hop uses the ordinary display decode
# (legal-range, cropped, no --cdr / --cdr-in anywhere in the chain).
#
# Usage: identical to genchain.sh:
#   genchain_bb.sh <master.yuv> <trueW> <trueH> <fmt 422|444> <depth> <bpp> \
#                  <slice_h(0=auto)> <gens> [extra encoder flags...]
#
# Runs: master -> enc -> dec(display) -> enc -> dec(display) -> ... <gens> times,
# re-encoding each display decode with the SAME command line as generation 1.
# PASS iff every generation's display decode is byte-identical to generation
# 1's, and every generation >= 2 writes a byte-identical bitstream.
# Also prints the gen-1 stream md5 and the per-cell gamut evidence
# (committed range + out-of-legal-range count, from a one-off gen-1 CDR probe
# that takes no part in the chain).
set -u
# OMC v5: resolve the codec tree ONCE, before any cd, and absolutely.
OMC_TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
E="${OMC_BIN:-$OMC_TREE}"
D="$(cd "$(dirname "$0")" && pwd)"
MASTER=$1; TW=$2; TH=$3; FMT=$4; DEPTH=$5; BPP=$6; SH=$7; GENS=$8; shift 8
EXTRA=("$@")
WORK="${GENCHAIN_TMP:-$(mktemp -d)}"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

WAL=$([ "$FMT" = 422 ] && echo 64 || echo 32)
CW=$(( (TW + WAL - 1) / WAL * WAL ))
RSH=$SH
if [ "$RSH" = 0 ]; then RSH=$([ "$TH" -le 720 ] && echo 8 || echo 16); fi
CH=$(( (TH + RSH - 1) / RSH * RSH ))
SHFLAG=()
[ "$SH" != 0 ] && SHFLAG=(--slice-h "$SH")

"$E/omc_enc" -i "$MASTER" -o "$WORK/g1.omc" -w "$TW" -h "$TH" --fmt "$FMT" \
    --depth "$DEPTH" --bpp "$BPP" "${SHFLAG[@]}" "${EXTRA[@]}" 2>"$WORK/enc1.log" \
    || { echo "FAIL enc-gen1 ($(tail -1 "$WORK/enc1.log"))"; exit 1; }
# A2 marker: the encoder reports any configuration that exceeds the 1 ms
# latency budget (including output conversion).  Carried into the RESULT LINE
# itself, not just prose: these cells are exactness coverage, and a reader
# skimming PASS lines must not mistake an over-budget slice height for a
# shippable configuration.
A2=""
if grep -q "WARNING A2" "$WORK/enc1.log" 2>/dev/null; then
    A2=" [A2:OVER $(sed -n 's/.*takes \([0-9.]*\) ms.*/\1/p' "$WORK/enc1.log" | head -1)ms NOT-SHIPPABLE]"
fi
"$E/omc_dec" -i "$WORK/g1.omc" -o "$WORK/g1.yuv" 2>/dev/null \
    || { echo "FAIL dec-gen1"; exit 1; }
# gamut evidence (probe only; the chain never touches this file)
"$E/omc_dec" -i "$WORK/g1.omc" --cdr -o "$WORK/probe.cdr" 2>/dev/null
GAMUT=$(python3 "$D/gamut_probe.py" "$WORK/probe.cdr" "$DEPTH")
rm -f "$WORK/probe.cdr"

prev="$WORK/g1.yuv"; fail=""
for g in $(seq 2 "$GENS"); do
    "$E/omc_enc" -i "$prev" -o "$WORK/gN.omc" -w "$TW" -h "$TH" \
        --fmt "$FMT" --depth "$DEPTH" --bpp "$BPP" "${SHFLAG[@]}" "${EXTRA[@]}" \
        2>"$WORK/encN.log" || { fail="enc-gen$g ($(tail -1 "$WORK/encN.log"))"; break; }
    "$E/omc_dec" -i "$WORK/gN.omc" -o "$WORK/gN.yuv" 2>/dev/null \
        || { fail="dec-gen$g"; break; }
    cmp -s "$WORK/g1.yuv" "$WORK/gN.yuv" || { fail="pixels-gen$g"; break; }
    if [ "$g" = 2 ]; then cp "$WORK/gN.omc" "$WORK/g2.omc"
    else cmp -s "$WORK/g2.omc" "$WORK/gN.omc" || { fail="stream-gen$g"; break; }
    fi
    cp "$WORK/gN.yuv" "$WORK/prev.yuv"; prev="$WORK/prev.yuv"
done

if [ -n "$fail" ]; then
    echo "FAIL $fail  [BB ${TW}x${TH}->${CW}x${CH} $FMT/${DEPTH}b bpp=$BPP sh=$RSH gens=$GENS ${EXTRA[*]:-}] $GAMUT"
    exit 1
fi
echo "PASS  [BB ${TW}x${TH}->${CW}x${CH} $FMT/${DEPTH}b bpp=$BPP sh=$RSH gens=$GENS ${EXTRA[*]:-}] g1.omc=$(md5sum <"$WORK/g1.omc" | cut -d' ' -f1)$A2 $GAMUT"

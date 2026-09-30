#!/bin/bash
# genchain.sh - T5 generation-exactness chain test.
#
# Usage:
#   genchain.sh <master.yuv> <trueW> <trueH> <fmt 422|444> <depth> <bpp> \
#               <slice_h(0=auto)> <gens> [extra encoder flags...]
#
# Runs: master -> enc -> dec(--cdr) -> enc(--cdr-in) -> dec(--cdr) -> ... <gens> times.
# PASS iff every generation's CDR decode is byte-identical to generation 1's,
# and every generation >= 2 writes a byte-identical bitstream.
# Prints one line: PASS/FAIL, the coded dims, and the gen-1 stream md5.
set -u
# OMC v5: resolve the codec tree ONCE, before any cd, and absolutely.
OMC_TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
E="${OMC_BIN:-$OMC_TREE}"
MASTER=$1; TW=$2; TH=$3; FMT=$4; DEPTH=$5; BPP=$6; SH=$7; GENS=$8; shift 8
EXTRA=("$@")
WORK="${GENCHAIN_TMP:-$(mktemp -d)}"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

# FREE-SPACE PRECONDITION (2026-08-27).
# A chain that runs out of disk mid-way produces short/absent frame files, and the
# byte-comparison then reports "FAIL pixels-genN" -- a filesystem condition wearing
# the costume of a generation-exactness defect.  This actually happened: the 4K and
# 8K cells of the v5.2 gamut reported FAIL at 6.5 GB free and PASS at 14 GB free,
# on the identical binary.  It is the same class as the missing-binary guard below
# it: assert the precondition, exit 99, and never let the environment be reported
# as a codec result.
#
# Requirement: one generation holds a decode (W*Hcoded*3 or *4 bytes per frame for
# 422/444 at 16 bits) plus a stream; GENS generations are kept for comparison.
# 3x that, with a 512 MB floor, is a safe bound.
_bpf=$(( TW * TH * 4 ))
[ "$FMT" = 444 ] && _bpf=$(( TW * TH * 6 ))
# A chain keeps GENS generations of decodes plus their streams.  An earlier version of
# this guard hardcoded "* 6 * 3" and ignored GENS entirely, so an 11-generation 1080p chain
# asserted only the 512 MB floor while actually needing ~3 GB -- and reported a false
# "FAIL pixels-genN" when the filesystem filled instead of exiting 99.  Charge frames x GENS.
_frames=${GENCHAIN_FRAMES:-6}
_need_kb=$(( _bpf * _frames * (GENS + 1) / 1024 ))
[ "$_need_kb" -lt 524288 ] && _need_kb=524288
_free_kb=$(df -P -k "$WORK" | awk 'NR==2 {print $4}')
if [ -n "$_free_kb" ] && [ "$_free_kb" -lt "$_need_kb" ]; then
    echo "FAIL precondition: only $(( _free_kb / 1024 )) MB free on the work filesystem, need $(( _need_kb / 1024 )) MB for ${TW}x${TH} ${FMT}/${DEPTH}b x ${GENS} generations. A chain that fills the disk reports a false pixels-genN failure -- free space and re-run."
    exit 99
fi

# coded geometry
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
"$E/omc_dec" -i "$WORK/g1.omc" --cdr -o "$WORK/g1.cdr" 2>/dev/null \
    || { echo "FAIL dec-gen1"; exit 1; }

prev="$WORK/g1.cdr"; fail=""
for g in $(seq 2 "$GENS"); do
    "$E/omc_enc" --cdr-in -i "$prev" -o "$WORK/gN.omc" -w "$CW" -h "$CH" \
        --display-w "$TW" --display-h "$TH" \
        --fmt "$FMT" --depth "$DEPTH" --bpp "$BPP" "${SHFLAG[@]}" "${EXTRA[@]}" \
        2>"$WORK/encN.log" || { fail="enc-gen$g ($(tail -1 "$WORK/encN.log"))"; break; }
    "$E/omc_dec" -i "$WORK/gN.omc" --cdr -o "$WORK/gN.cdr" 2>/dev/null \
        || { fail="dec-gen$g"; break; }
    cmp -s "$WORK/g1.cdr" "$WORK/gN.cdr" || { fail="pixels-gen$g"; break; }
    if [ "$g" = 2 ]; then cp "$WORK/gN.omc" "$WORK/g2.omc"
    else cmp -s "$WORK/g2.omc" "$WORK/gN.omc" || { fail="stream-gen$g"; break; }
    fi
    cp "$WORK/gN.cdr" "$WORK/prev.cdr"; prev="$WORK/prev.cdr"
done

if [ -n "$fail" ]; then
    echo "FAIL $fail  [${TW}x${TH}->${CW}x${CH} $FMT/${DEPTH}b bpp=$BPP sh=$RSH gens=$GENS ${EXTRA[*]:-}]$A2"
    exit 1
fi
echo "PASS  [${TW}x${TH}->${CW}x${CH} $FMT/${DEPTH}b bpp=$BPP sh=$RSH gens=$GENS ${EXTRA[*]:-}] g1.omc=$(md5sum <"$WORK/g1.omc" | cut -d' ' -f1)$A2"

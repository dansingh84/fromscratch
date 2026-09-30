#!/bin/bash
# antsmatrix.sh -- the temporal-stability ("ants") matrix, and its cost.
#
# For every cell of the corpus and every arm named below it prints, on one line,
# the ants tail of the DECODE and of the SOURCE on all three planes, and the
# VMAF-NEG of that decode against the same master.  Those are the two numbers a
# candidate fix has to move in the right direction at the same time: a fix that
# calms the picture by removing texture shows up as a VMAF-NEG loss in the last
# column, and a fix that hides the defect by adding energy cannot gain there at
# all (that is what the NEG model is for).  See docs/TEMPORAL_T5.md 12.23.
#
#   tail = P(|frame-to-frame difference| > 6 codes) over blocks the SOURCE holds
#          flat and static -- docs/REPORT.md 18.6, generalised off luma
#
# The source column is the target, not zero: real footage has grain and grain
# moves.  A decode BELOW its source column has the incumbent's "sub-source calm".
#
# Requires: tests/ants.py, tests/vmafneg.sh (and libvmaf -- see that script's
# header), the masters of section 10.1, and a v4.14 tree if the v4.14 column is
# wanted.
#
#   usage:  antsmatrix.sh [bpp ...]            (default: 0.5 1.0 2.0)
#   env:    OMC_BIN   directory holding the omc_enc/omc_dec under test
#           OMC_BIN_REF  optional: a second tree to print as the "reference"
#                     column (this project used the v4.14 drop)
set -u
# OMC v5: resolve the codec tree ONCE, before any cd, and absolutely.  The
# tree is the parent of tests/.  Resolving after a cd, or with a bare
# relative path, breaks depending on where the script was invoked from.
OMC_TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$(dirname "$0")/.."
E="${OMC_BIN:-$OMC_TREE}"
REF="${OMC_BIN_REF:-}"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
RATES=${*:-"0.5 1.0 2.0"}

cell() {  # <tree> <env-assignments> <flags> <master> <w> <h> <fmt> <depth> <bpp> <label>
  local t=$1 ev=$2 fl=$3 m=$4 w=$5 h=$6 f=$7 d=$8 b=$9 lab=${10}
  env $ev "$t/omc_enc" -i "$m" -o "$TMP/a.omc" -w "$w" -h "$h" --fmt "$f" \
      --depth "$d" --bpp "$b" $fl >/dev/null 2>&1 || { printf "  %-24s ENCODE FAILED\n" "$lab"; return; }
  "$t/omc_dec" -i "$TMP/a.omc" -o "$TMP/a.yuv" >/dev/null 2>&1
  read -r yt ys cbt cbs crt crs <<<"$(python3 tests/ants.py "$m" "$TMP/a.yuv" "$w" "$h" "$f" "$d" |
      awk '/^Y /{yt=$3;ys=$5} /^Cb /{cbt=$3;cbs=$5} /^Cr /{crt=$3;crs=$5} END{print yt,ys,cbt,cbs,crt,crs}')"
  # the project's OWN thresholds (docs/REPORT.md 18.7).  They select far fewer
  # blocks and on some content none at all, which is why the relaxed pair above
  # carries the main table and this one is reported beside it rather than
  # instead of it.
  read -r syt sys <<<"$(python3 tests/ants.py "$m" "$TMP/a.yuv" "$w" "$h" "$f" "$d" --strict |
      awk '/^Y /{yt=$3;ys=$5} END{print yt,ys}')"
  local v; v=$(bash tests/vmafneg.sh "$m" "$TMP/a.yuv" "$w" "$h" "$f" "$d" |
      sed -n 's/.*mean \([0-9.]*\).*/\1/p')
  printf "  %-24s Y %6s/%-6s Cb %6s/%-6s Cr %6s/%-6s | strict Y %6s/%-6s | NEG %s\n" \
         "$lab" "$yt" "$ys" "$cbt" "$cbs" "$crt" "$crs" "$syt" "$sys" "${v:-n/a}"
}

for arm in "tests/raw/still1080_422_10.yuv 1920 1080 422 10" \
           "tests/raw/loop1080_422_10.yuv 1920 1080 422 10" \
           "tests/raw/still720_444_8.yuv 1280 720 444 8" \
           "tests/raw/gfx1080_fullrange_422_10.yuv 1920 1080 422 10" \
           "tests/raw/gfx1080_422_10.yuv 1920 1080 422 10" \
           "tests/raw/gfx1080_444_12.yuv 1920 1080 444 12" \
           "tests/raw/cineA21_444_10.yuv 2048 1152 444 10" \
           "tests/raw/cineA21_422_12.yuv 2048 1152 422 12" \
           "tests/raw/cineA31_720_444_8.yuv 1280 720 444 8" \
           "tests/raw/cine4k_422_8.yuv 4096 2160 422 8" \
           "tests/raw/gfxF003_444_8.yuv 4480 1856 444 8"; do
  set -- $arm
  for b in $RATES; do
    echo "=== $(basename "$1" .yuv) @ $b   decode-tail/source-tail %"
    [ -n "$REF" ] && cell "$REF" "" ""                      "$1" "$2" "$3" "$4" "$5" "$b" "reference build"
    cell "$E" "OMC_CALM=0" "--fill"                          "$1" "$2" "$3" "$4" "$5" "$b" "ants fix off, fill on"
    cell "$E" "OMC_CALM=0" ""                                "$1" "$2" "$3" "$4" "$5" "$b" "ants fix off, fill off"
    cell "$E" "" "--fill"                                    "$1" "$2" "$3" "$4" "$5" "$b" "shipped fix, fill on"
    cell "$E" "" ""                                          "$1" "$2" "$3" "$4" "$5" "$b" "SHIPPED DEFAULTS"
  done
done
echo ANTSMATRIX-DONE

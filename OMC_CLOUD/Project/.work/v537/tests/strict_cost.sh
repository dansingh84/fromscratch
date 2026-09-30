#!/bin/bash
# strict_cost.sh -- what --gamut-strict costs, per cell, at generation 1.
#
# For each cell: encode with the mode OFF and ON, decode both, and score both
# against the master with VMAF-NEG (the metric that decides) and PSNR (second
# opinion).  Also prints the gamut count for each and whether the two streams
# are byte-identical -- on content that never leaves the legal range they must
# be, because the repair has nothing to fire on.
#
#   strict_cost.sh [passes]      (default 4)
set -u
# OMC v5: resolve the codec tree ONCE, before any cd, and absolutely.
OMC_TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$(dirname "$0")/.."
# OMC_BIN lets a measurement run pin the binaries it measures, exactly as the
# chain harnesses do -- a rebuild mid-battery otherwise swaps the encoder
# underneath the comparison.
E="${OMC_BIN:-$OMC_TREE}"; R="$OMC_TREE/tests/raw"
P=${1:-4}
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT

cell() { # master W H fmt depth bpp slice_h
  local m=$1 w=$2 h=$3 f=$4 d=$5 b=$6 s=$7
  local sf=(); [ "$s" != 0 ] && sf=(--slice-h "$s")
  local o1 o2 g1 g2 v1 v2 p1 p2 same
  $E/omc_enc -i "$m" -o "$W/off.omc" -w "$w" -h "$h" --fmt "$f" --depth "$d" \
      --bpp "$b" "${sf[@]}" 2>"$W/off.log" >/dev/null
  $E/omc_enc -i "$m" -o "$W/on.omc"  -w "$w" -h "$h" --fmt "$f" --depth "$d" \
      --bpp "$b" "${sf[@]}" --gamut-strict "$P" 2>"$W/on.log" >/dev/null
  g1=$(sed -n 's/.*gamut: \([0-9]*\) committed.*/\1/p' "$W/off.log")
  g2=$(sed -n 's/.*gamut: \([0-9]*\) committed.*/\1/p' "$W/on.log")
  $E/omc_dec -i "$W/off.omc" -o "$W/off.yuv" 2>/dev/null
  $E/omc_dec -i "$W/on.omc"  -o "$W/on.yuv"  2>/dev/null
  v1=$(bash tests/vmafneg.sh "$m" "$W/off.yuv" "$w" "$h" "$f" "$d" | sed -n 's/.*mean \([0-9.]*\).*/\1/p')
  v2=$(bash tests/vmafneg.sh "$m" "$W/on.yuv"  "$w" "$h" "$f" "$d" | sed -n 's/.*mean \([0-9.]*\).*/\1/p')
  p1=$(python3 tests/quality.py "$m" "$W/off.yuv" "$w" "$h" "$f" "$d" "$s" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="Y"){s+=$(i+1);n++}} END{if(n)printf "%.2f",s/n}')
  p2=$(python3 tests/quality.py "$m" "$W/on.yuv"  "$w" "$h" "$f" "$d" "$s" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="Y"){s+=$(i+1);n++}} END{if(n)printf "%.2f",s/n}')
  cmp -s "$W/off.omc" "$W/on.omc" && same=IDENTICAL || same=differs
  printf "%-24s %sx%s %s/%-2s bpp=%-4s sh=%-2s oob %8s -> %-8s VMAF-NEG %7s -> %-7s  PSNR-Y %6s -> %-6s  stream %s\n" \
    "$(basename "$m" .yuv)" "$w" "$h" "$f" "$d" "$b" "$s" "$g1" "$g2" "$v1" "$v2" "$p1" "$p2" "$same"
}

cell $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16   # control: oob = 0 already
cell $R/gfx1080_fullrange_422_10.yuv    1920 1080 422 10 0.5 16
cell $R/gfx1080_fullrange_422_10.yuv    1920 1080 422 10 1.0 16
cell $R/rail720_422_10.yuv     1280 720  422 10 0.5 0
cell $R/rail720_422_10.yuv     1280 720  422 10 1.0 0
cell $R/cineA31_720_444_8.yuv  1280 720  444 8  0.5 0
cell $R/cineA31_720_444_8.yuv  1280 720  444 8  1.0 16
cell $R/cineA21_444_10.yuv     2048 1152 444 10 2.0 16
cell $R/gfx1080_444_12.yuv     1920 1080 444 12 0.5 16
cell $R/gfxF003_444_8.yuv      4480 1856 444 8  0.5 16
cell $R/cine4k_444_10.yuv      4096 2160 444 10 2.0 32
echo STRICTCOST-DONE

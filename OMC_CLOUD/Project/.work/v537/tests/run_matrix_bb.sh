#!/bin/bash
# run_matrix_bb.sh - the T5 generation-exactness matrix over PURE BASEBAND
# interchange (tests/genchain_bb.sh): every cell of run_matrix.sh, split by
# geometry.  "padfree" cells have coded == display raster (no pad rows);
# "padded" cells (1080-coded-as-1088, 2160-as-2176 at sh32) require the
# transform-domain pad synthesis (minor 11) to hold over baseband.
#   usage: run_matrix_bb.sh padfree|padded|all
set -u
cd "$(dirname "$0")/.."
T=tests/genchain_bb.sh; R="$OMC_TREE/tests/raw"
MODE=${1:-padfree}

padfree() {
$T $R/gfx720_422_10.yuv      1280 720  422 10 0.5 0  6
$T $R/gfx720_422_10.yuv      1280 720  422 10 2.0 0  5
$T $R/cineA31_720_444_8.yuv  1280 720  444 8  0.5 0  5
$T $R/cineA31_720_444_8.yuv  1280 720  444 8  1.0 16 5
$T $R/cineA21_720_422_12.yuv 1280 720  422 12 3.0 0  5
$T $R/cineA21_422_12.yuv     2048 1152 422 12 0.5 16 6
$T $R/cineA21_444_10.yuv     2048 1152 444 10 2.0 16 5
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 8  5
$T $R/cineA31_422_10.yuv     2048 1152 422 10 3.0 32 5
$T $R/cine4k_422_8.yuv       4096 2160 422 8  0.5 16 4
$T $R/gfxF003_444_8.yuv      4480 1856 444 8  0.5 16 4
$T $R/gfxF003_422_12.yuv     4480 1856 422 12 1.0 8  4
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 16 5 --tune vmaf
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 16 5 --grain-corr --fill-static
}

padded() {
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 0.5 16 6
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 3.0 16 5
$T $R/gfx1080_444_12.yuv     1920 1080 444 12 0.5 16 6
$T $R/gfx1080_444_12.yuv     1920 1080 444 12 3.0 16 5
$T $R/gfx1080_444_8.yuv      1920 1080 444 8  1.0 16 5
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 32 5
$T $R/cine4k_444_10.yuv      4096 2160 444 10 2.0 32 4
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --tune vmaf
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --grain-corr
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --fill-static
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --no-fill
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --grain-replace
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --refresh 2
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --refresh 3
}

case $MODE in
  padfree) padfree ;;
  padded)  padded ;;
  all)     padfree; padded ;;
  *) echo "usage: run_matrix_bb.sh padfree|padded|all" >&2; exit 2 ;;
esac

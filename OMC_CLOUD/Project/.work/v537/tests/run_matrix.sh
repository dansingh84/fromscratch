#!/bin/bash
# run_matrix.sh - the full T5 generation-exactness matrix over the provided
# footage: every resolution class (720p, 1080p, 1152p, 4K DCI, 4480-wide),
# depths 8/10/12, 4:2:2 and 4:4:4, rates 0.5..3.0 bpp, slice heights 8/16/32,
# and the encoder option set.  Each line: PASS/FAIL from tests/genchain.sh.
set -u
cd "$(dirname "$0")/.."
T=tests/genchain.sh; R="$OMC_TREE/tests/raw"

# --- 720p class (slice_h 8 default + explicit 16) ---
$T $R/gfx720_422_10.yuv      1280 720  422 10 0.5 0  6
$T $R/gfx720_422_10.yuv      1280 720  422 10 2.0 0  5
$T $R/cineA31_720_444_8.yuv  1280 720  444 8  0.5 0  5
$T $R/cineA31_720_444_8.yuv  1280 720  444 8  1.0 16 5
$T $R/cineA21_720_422_12.yuv 1280 720  422 12 3.0 0  5

# --- 1080p class (1080 codes as 1088: the pad-and-crop path) ---
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 0.5 16 6
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 3.0 16 5
$T $R/gfx1080_444_12.yuv     1920 1080 444 12 0.5 16 6
$T $R/gfx1080_444_12.yuv     1920 1080 444 12 3.0 16 5
$T $R/gfx1080_444_8.yuv      1920 1080 444 8  1.0 16 5
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 32 5

# --- 2048x1152 class ---
$T $R/cineA21_422_12.yuv     2048 1152 422 12 0.5 16 6
$T $R/cineA21_444_10.yuv     2048 1152 444 10 2.0 16 5
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 8  5
$T $R/cineA31_422_10.yuv     2048 1152 422 10 3.0 32 5

# --- 4K DCI class ---
$T $R/cine4k_422_8.yuv       4096 2160 422 8  0.5 16 4
$T $R/cine4k_444_10.yuv      4096 2160 444 10 2.0 32 4

# --- 4480x1856 class ---
$T $R/gfxF003_444_8.yuv      4480 1856 444 8  0.5 16 4
$T $R/gfxF003_422_12.yuv     4480 1856 422 12 1.0 8  4

# --- encoder options (all on the 1080p 4:2:2/10 master) ---
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --tune vmaf
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --grain-corr
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --fill-static
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --no-fill
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --grain-replace
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --refresh 2
$T $R/gfx1080_422_10.yuv     1920 1080 422 10 1.0 16 5 --refresh 3
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 16 5 --tune vmaf
$T $R/cineA31_422_10.yuv     2048 1152 422 10 0.5 16 5 --grain-corr --fill-static

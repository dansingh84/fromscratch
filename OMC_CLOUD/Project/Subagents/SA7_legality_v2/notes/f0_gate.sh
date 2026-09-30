#!/bin/bash
# [SA7/F0] Byte-identity gate: f0tree2 vs the pristine control, shipped defaults.
# One point at a time. Unique output paths per point. All four exit codes captured.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
NEW=$A/f0tree2; BASE=$A/basectl
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
O=$A/out/F0G; mkdir -p "$O"
NF=${NF:-8}
run() {   # tag src w h fmt depth bpp
  local tag=$1 src=$2 w=$3 h=$4 fmt=$5 dep=$6 bpp=$7
  local p="$O/${tag}_${fmt}_${dep}_${bpp}"
  local r1 r2 r3 r4
  nice -n 19 "$NEW/omc_enc"  -i "$src" -o "$p.new.omc" -w $w -h $h --fmt $fmt --depth $dep --bpp $bpp -n $NF >"$p.new.enc.log" 2>&1; r1=$?
  nice -n 19 "$BASE/omc_enc" -i "$src" -o "$p.bas.omc" -w $w -h $h --fmt $fmt --depth $dep --bpp $bpp -n $NF >"$p.bas.enc.log" 2>&1; r2=$?
  nice -n 19 "$NEW/omc_dec"  -i "$p.new.omc" -o "$p.new.yuv" >"$p.new.dec.log" 2>&1; r3=$?
  nice -n 19 "$BASE/omc_dec" -i "$p.bas.omc" -o "$p.bas.yuv" >"$p.bas.dec.log" 2>&1; r4=$?
  local s d
  cmp -s "$p.new.omc" "$p.bas.omc"; s=$?
  cmp -s "$p.new.yuv" "$p.bas.yuv"; d=$?
  echo "GATE $tag $fmt/$dep @$bpp rc=$r1/$r2/$r3/$r4 stream=$s decode=$d"
  rm -f "$p.new.yuv" "$p.bas.yuv"
}
run dng720  $ARMS/dng_1280x720_422_10.yuv            1280  720 422 10 0.5
run dng720  $ARMS/dng_1280x720_422_10.yuv            1280  720 422 10 1.0
run dng720  $ARMS/dng_1280x720_422_10.yuv            1280  720 422 10 2.0
run gfx     $ARMS/cf_gfx_448x256_422_10.yuv           448  256 422 10 0.5
run gfx     $ARMS/cf_gfx_448x256_422_10.yuv           448  256 422 10 1.0
run gfx     $ARMS/cf_gfx_448x256_422_10.yuv           448  256 422 10 2.0
run spot    $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 0.5
run spot    $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 1.0
run spot    $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 2.0
run dng1080 $ARMS/dng_1920x1080_422_10.yuv           1920 1080 422 10 0.5
run dng1080 $ARMS/dng_1920x1080_422_10.yuv           1920 1080 422 10 1.0
run dng1080 $ARMS/dng_1920x1080_422_10.yuv           1920 1080 422 10 2.0
run dng444  $ARMS/dng_1920x1080_444_12.yuv           1920 1080 444 12 0.5
run dng444  $ARMS/dng_1920x1080_444_12.yuv           1920 1080 444 12 1.0
run dng444  $ARMS/dng_1920x1080_444_12.yuv           1920 1080 444 12 2.0
run dng8    $ARMS/dng_1920x1080_422_8.yuv            1920 1080 422  8 0.5
run dng8    $ARMS/dng_1920x1080_422_8.yuv            1920 1080 422  8 1.0
run dng8    $ARMS/dng_1920x1080_422_8.yuv            1920 1080 422  8 2.0
echo GATE_DONE

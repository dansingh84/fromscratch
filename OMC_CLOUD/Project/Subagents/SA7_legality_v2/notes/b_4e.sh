#!/bin/bash
# [SA7-4e] THE COMPOSITE: cap (K=4) + escapes as input-side stages, then the
# SHIPPED repair engine for the residue -- against the base running the shipped
# engine alone.  PC-all off, constructive pass off.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/btree1/omc_enc; D=$A/btree1/omc_dec; O=$A/out/B4E; mkdir -p "$O"
run() {  # tag src w h fmt dep nf bpp arm
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8 arm=$9
  local b="$O/${t}_${bp}_${arm}" rc1 rc2 EV=""
  [ "$arm" = comp ] && EV="OMC_BCAP=1 OMC_BCAP_K=4 OMC_BESC=1"
  env $EV nice -n 19 "$E" -i "$src" -o "$b.omc" -w $w -h $h --fmt $fm --depth $dp \
      --bpp $bp -n $nf > "$b.log" 2>&1; rc1=$?
  nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dl" 2>&1; rc2=$?
  local oob sl pas worst p50 p90 safe
  oob=$(grep -oE 'gamut: [0-9]+' "$b.log" | grep -oE '[0-9]+' | head -1)
  sl=$(grep -oE '[0-9]+ slices repaired' "$b.log" | grep -oE '[0-9]+' | head -1)
  pas=$(grep -oE 'repaired in [0-9]+ passes' "$b.log" | grep -oE '[0-9]+' | head -1)
  worst=$(grep -oE 'worst total passes [0-9]+' "$b.log" | grep -oE '[0-9]+' | head -1)
  p50=$(grep -oE 'p50 [0-9]+' "$b.log" | grep -oE '[0-9]+' | head -1)
  p90=$(grep -oE 'p90 [0-9]+' "$b.log" | grep -oE '[0-9]+' | head -1)
  safe=$(grep -oE 'baseband-safe: [a-zA-Z]+' "$b.log" | awk '{print $2}')
  echo "B4E $t $fm/$dp @$bp arm=$arm rc=$rc1/$rc2 oob=${oob:-NA} safe=${safe:-NA} slices_repaired=${sl:-0} total_passes=${pas:-0} worst_passes=${worst:-0} p50=${p50:-0} p90=${p90:-0} bytes=$( [ -f $b.omc ] && stat -c %s $b.omc || echo NA)"
  if [ $rc2 -eq 0 ]; then
    python3 "$A/notes/po_psnr.py" "$src" "$b.yuv" $w $h $fm $dp $nf "$t @$bp $arm"
  fi
  rm -f "$b.yuv" "$b.omc"; }
for c in "dng720 $ARMS/dng_1280x720_422_10.yuv 1280 720 422 10 4 0.5" \
         "gfx $ARMS/cf_gfx_448x256_422_10.yuv 448 256 422 10 4 0.5" \
         "spot $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 4 0.5" \
         "spot $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 4 1.0" \
         "dng444 $ARMS/dng_1920x1080_444_12.yuv 1920 1080 444 12 4 0.5" \
         "cut24 $A/arms/cut24.yuv 256 64 422 10 24 1.0" \
         "extLIM $A/arms/ext_10_422_l1.yuv 512 128 422 10 4 1.0"; do
  set -- $c
  run $1 $2 $3 $4 $5 $6 $7 $8 base
  run $1 $2 $3 $4 $5 $6 $7 $8 comp
done
echo B4E_DONE

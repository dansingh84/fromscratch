#!/bin/bash
# [SA7-PO] DESIGN3 gate (3): compression at equal CBR against the frozen base.
# Arms: base (shipped transform, shipped defaults) | PO two-tap | PO four-tap (1,7,7,1)/16.
# Bar: no plane of any cell worse than 0.1 dB.  Worst frame reported.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/ptree6/omc_enc; D=$A/ptree6/omc_dec; O=$A/out/PO3; mkdir -p "$O"
NF=8
one() {  # tag src w h fmt dep bpp arm
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 bp=$7 arm=$8
  local b="$O/${t}_${bp}_${arm}" rc1 rc2
  case $arm in
    base) env OMC_GM_LATT=1 nice -n 19 "$E" -i "$src" -o "$b.omc" -w $w -h $h --fmt $fm \
            --depth $dp --bpp $bp -n $NF > "$b.enc.log" 2>&1; rc1=$?
          nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dec.log" 2>&1; rc2=$? ;;
    *)    local ww=${arm#w}
          OMC_PO=1 OMC_PO_W=$ww OMC_PO_CAP=1 OMC_GM_LATT=0 nice -n 19 "$E" \
            -i "$src" -o "$b.omc" -w $w -h $h --fmt $fm --depth $dp --bpp $bp -n $NF \
            --gamut-strict 0 > "$b.enc.log" 2>&1; rc1=$?
          OMC_PO=1 OMC_PO_W=$ww nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dec.log" 2>&1; rc2=$? ;;
  esac
  local oob bytes
  oob=$(grep -oE 'gamut: [0-9]+' "$b.enc.log" | grep -oE '[0-9]+')
  bytes=$( [ -f "$b.omc" ] && stat -c %s "$b.omc" || echo NA )
  if [ $rc1 -eq 0 ] && [ $rc2 -eq 0 ]; then
    python3 "$A/notes/po_psnr.py" "$src" "$b.yuv" $w $h $fm $dp $NF \
        "$t @$bp $arm bytes=$bytes oob=${oob:-NA} rc=$rc1/$rc2"
  else
    echo "PSNR $t @$bp $arm FAILED rc=$rc1/$rc2 oob=${oob:-NA}"
  fi
  rm -f "$b.yuv" "$b.omc"
}
cell() {  # tag src w h fmt dep
  for bp in 0.5 1.0 2.0 4.0; do
    for arm in base w0 w1; do one "$1" "$2" $3 $4 $5 $6 $bp $arm; done
  done
}
cell dng720   $ARMS/dng_1280x720_422_10.yuv            1280  720 422 10
cell gfx      $ARMS/cf_gfx_448x256_422_10.yuv           448  256 422 10
cell dng1080  $ARMS/dng_1920x1080_422_10.yuv           1920 1080 422 10
cell dng444   $ARMS/dng_1920x1080_444_12.yuv           1920 1080 444 12
cell spot     $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10
cell floorb   $ARMS/long/floorballgameL_1920x1080_422_10.yuv 1920 1080 422 10
echo GATE3_DONE

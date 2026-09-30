#!/bin/bash
# [SA7-B] L-I28 oracle, measurements (3) PSNR at equal CBR and (4) the chain.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/btree1/omc_enc; D=$A/btree1/omc_dec; O=$A/out/B1Q; mkdir -p "$O"
NF=8
psnr() {  # tag src w h fmt dep bpp arm
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 bp=$7 arm=$8
  local b="$O/${t}_${bp}_${arm}" r1 r2
  if [ "$arm" = base ]; then
    nice -n 19 "$E" -i "$src" -o "$b.omc" -w $w -h $h --fmt $fm --depth $dp \
        --bpp $bp -n $NF > "$b.enc.log" 2>&1; r1=$?
  else
    OMC_BCAP=1 OMC_BCAP_CAP=1 OMC_GM_LATT=0 nice -n 19 "$E" -i "$src" -o "$b.omc" \
        -w $w -h $h --fmt $fm --depth $dp --bpp $bp -n $NF --gamut-strict 0 \
        > "$b.enc.log" 2>&1; r1=$?
  fi
  nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dec.log" 2>&1; r2=$?
  local oob bytes
  oob=$(grep -oE 'gamut: [0-9]+' "$b.enc.log" | grep -oE '[0-9]+')
  bytes=$( [ -f "$b.omc" ] && stat -c %s "$b.omc" || echo NA )
  if [ $r1 -eq 0 ] && [ $r2 -eq 0 ]; then
    python3 "$A/notes/po_psnr.py" "$src" "$b.yuv" $w $h $fm $dp $NF \
        "$t @$bp $arm bytes=$bytes oob=${oob:-NA} rc=$r1/$r2"
  else echo "PSNR $t @$bp $arm FAILED rc=$r1/$r2"; fi
  rm -f "$b.yuv" "$b.omc"
}
for bp in 0.5 1.0 2.0; do for arm in base bcap; do
  psnr dng720 $ARMS/dng_1280x720_422_10.yuv 1280 720 422 10 $bp $arm
  psnr gfx    $ARMS/cf_gfx_448x256_422_10.yuv 448 256 422 10 $bp $arm
done; done
echo "--- (4) the 8-generation chain through the display decode, cap armed ---"
chain() {  # tag src w h nf
  local t=$1 src=$2 w=$3 h=$4 nf=$5 IN="$2" prev_pic="" prev_str="" g rc pic str mv ss oob
  for g in 1 2 3 4 5 6 7 8; do
    local b="$O/ch_${t}_g$g"
    OMC_BCAP=1 OMC_BCAP_CAP=1 OMC_GM_LATT=0 nice -n 19 "$E" -i "$IN" -o "$b.omc" \
       -w $w -h $h --fmt 422 --depth 10 --bpp 0.5 -n $nf --gamut-strict 0 \
       > "$b.enc.log" 2>&1; rc=$?
    [ $rc -ne 0 ] && { echo "CHAIN $t g$g ENC rc=$rc"; return 1; }
    nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dec.log" 2>&1; rc=$?
    [ $rc -ne 0 ] && { echo "CHAIN $t g$g DEC rc=$rc"; return 1; }
    pic=$(md5sum < "$b.yuv" | cut -d' ' -f1); str=$(md5sum < "$b.omc" | cut -d' ' -f1)
    mv="-"; ss="-"
    [ -n "$prev_pic" ] && { [ "$pic" = "$prev_pic" ] && mv=0 || mv=MOVED; }
    [ -n "$prev_str" ] && { [ "$str" = "$prev_str" ] && ss=SAME || ss=DIFF; }
    oob=$(grep -oE 'gamut: [0-9]+' "$b.enc.log" | grep -oE '[0-9]+')
    echo "CHAIN $t g$g picture_vs_prev=$mv stream_vs_prev=$ss oob=${oob:-NA}"
    prev_pic=$pic; prev_str=$str
    [ $g -gt 1 ] && rm -f "$O/ch_${t}_g$((g-1)).yuv"
    IN="$b.yuv"
  done
  rm -f "$O/ch_${t}_g8.yuv" "$O"/ch_${t}_g*.omc
}
chain dng720 $ARMS/dng_1280x720_422_10.yuv 1280 720 8
chain spot   $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 8
echo B1Q_DONE

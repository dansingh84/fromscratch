#!/bin/bash
# [SA7-B] L-I28 oracle measurement (4): the 8-generation chain, cap armed.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
E=$A/btree1/omc_enc; D=$A/btree1/omc_dec; O=$A/out/B1C; mkdir -p "$O"
chain() {  # tag src w h nf
  local t=$1 IN=$2 w=$3 h=$4 nf=$5 prev_pic="" prev_str="" g rc pic str mv ss oob
  for g in 1 2 3 4 5 6 7 8; do
    local b="$O/${t}_g$g"
    OMC_BCAP=1 OMC_BCAP_CAP=1 OMC_GM_LATT=0 nice -n 19 "$E" -i "$IN" -o "$b.omc" \
       -w $w -h $h --fmt 422 --depth 10 --bpp 0.5 -n $nf --gamut-strict 0 \
       > "$b.enc.log" 2>&1; rc=$?
    [ $rc -ne 0 ] && { echo "CHAIN $t g$g ENC rc=$rc"; return 1; }
    nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dec.log" 2>&1; rc=$?
    [ $rc -ne 0 ] && { echo "CHAIN $t g$g DEC rc=$rc"; return 1; }
    pic=$(md5sum < "$b.yuv" | cut -d' ' -f1); str=$(md5sum < "$b.omc" | cut -d' ' -f1)
    mv="-"; ss="-"
    [ -n "$prev_pic" ] && { [ "$pic" = "$prev_pic" ] && mv=LOCKED || mv=MOVED; }
    [ -n "$prev_str" ] && { [ "$str" = "$prev_str" ] && ss=SAME || ss=DIFF; }
    oob=$(grep -oE 'gamut: [0-9]+' "$b.enc.log" | grep -oE '[0-9]+')
    echo "CHAIN $t g$g picture_vs_prev=$mv stream_vs_prev=$ss oob=${oob:-NA}"
    prev_pic=$pic; prev_str=$str
    [ $g -gt 1 ] && rm -f "$O/${t}_g$((g-1)).yuv"
    IN="$b.yuv"
  done
  rm -f "$O/${t}_g8.yuv" "$O"/${t}_g*.omc
}
chain dng720 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv 1280 720 8
chain spot /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 8
echo B1C_DONE

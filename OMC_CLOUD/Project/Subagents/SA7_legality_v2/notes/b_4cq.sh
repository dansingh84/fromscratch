#!/bin/bash
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/btree1/omc_enc; D=$A/btree1/omc_dec; O=$A/out/B4Q; mkdir -p "$O"
q() { local t=$1 src=$2 w=$3 h=$4 bp=$5 arm=$6; local b="$O/${t}_${bp}_${arm}"; local r1 r2
  if [ "$arm" = base ]; then nice -n 19 "$E" -i "$src" -o "$b.omc" -w $w -h $h --fmt 422 \
        --depth 10 --bpp $bp -n 8 > "$b.log" 2>&1; r1=$?
  else OMC_BCAP=1 OMC_BCAP_K=4 OMC_BESC=1 OMC_GM_LATT=0 nice -n 19 "$E" -i "$src" -o "$b.omc" \
        -w $w -h $h --fmt 422 --depth 10 --bpp $bp -n 8 --gamut-strict 0 > "$b.log" 2>&1; r1=$?; fi
  nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dl" 2>&1; r2=$?
  [ $r1 -eq 0 ] && [ $r2 -eq 0 ] && python3 "$A/notes/po_psnr.py" "$src" "$b.yuv" $w $h 422 10 8 \
      "$t @$bp $arm bytes=$(stat -c %s $b.omc) oob=$(grep -oE 'gamut: [0-9]+' $b.log|grep -oE '[0-9]+') rc=$r1/$r2" \
      || echo "PSNR $t @$bp $arm FAILED rc=$r1/$r2"
  rm -f "$b.yuv" "$b.omc"; }
for bp in 0.5 1.0 2.0; do
  q dng720 $ARMS/dng_1280x720_422_10.yuv 1280 720 $bp base
  q dng720 $ARMS/dng_1280x720_422_10.yuv 1280 720 $bp armed
  q gfx $ARMS/cf_gfx_448x256_422_10.yuv 448 256 $bp base
  q gfx $ARMS/cf_gfx_448x256_422_10.yuv 448 256 $bp armed
done
echo "--- chain, cap + escapes armed ---"
ch() { local t=$1 IN=$2 w=$3 h=$4; local pp="" ps=""; local g rc pic str mv ss oob
  for g in 1 2 3 4 5 6 7 8; do local b="$O/ch_${t}_g$g"
    OMC_BCAP=1 OMC_BCAP_K=4 OMC_BESC=1 OMC_GM_LATT=0 nice -n 19 "$E" -i "$IN" -o "$b.omc" \
      -w $w -h $h --fmt 422 --depth 10 --bpp 0.5 -n 8 --gamut-strict 0 > "$b.log" 2>&1; rc=$?
    [ $rc -ne 0 ] && { echo "CHAIN $t g$g ENC rc=$rc"; return 1; }
    nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dl" 2>&1; rc=$?
    [ $rc -ne 0 ] && { echo "CHAIN $t g$g DEC rc=$rc"; return 1; }
    pic=$(md5sum < "$b.yuv"|cut -d' ' -f1); str=$(md5sum < "$b.omc"|cut -d' ' -f1)
    mv="-"; ss="-"; [ -n "$pp" ] && { [ "$pic" = "$pp" ] && mv=LOCKED || mv=MOVED; }
    [ -n "$ps" ] && { [ "$str" = "$ps" ] && ss=SAME || ss=DIFF; }
    oob=$(grep -oE 'gamut: [0-9]+' "$b.log"|grep -oE '[0-9]+')
    echo "CHAIN $t g$g picture=$mv stream=$ss oob=${oob:-NA}"
    pp=$pic; ps=$str; [ $g -gt 1 ] && rm -f "$O/ch_${t}_g$((g-1)).yuv"; IN="$b.yuv"
  done; rm -f "$O/ch_${t}_g8.yuv" "$O"/ch_${t}_g*.omc; }
ch dng720 $ARMS/dng_1280x720_422_10.yuv 1280 720
ch spot $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080
echo B4Q_DONE

#!/bin/bash
set -u
. notes/cells.sh
r(){ C=$1; S=$2; W=$3; H=$4; SH=$5
 for a in bdec dec; do
   D=out/P/${C}_b0.5.$a.yuv; [ -f "$D" ] || { echo "missing $D"; continue; }
   if [ $H -eq 1080 ]; then python3 notes/crop.py $D out/P/tmp.yuv 1920 1088 1080 12; D=out/P/tmp.yuv; fi
   n=base; [ $a = dec ] && n=twophase
   python3 notes/gridmap.py "$S" $D $W $H 422 10 8 renders/${C}_f8_2ph_$n --sh $SH --grid 64
   python3 notes/phase.py  "$S" $D $W $H 422 10 8 64
   python3 ../shared_tools/planepsnr.py "$S" $D $W $H 422 10 ${C}_$n
 done; rm -f out/P/tmp.yuv
}
r spot   "$ARMS/long/spotrobotL_1920x1080_422_10.yuv" 1920 1080 16
r dng720 "$ARMS/dng_1280x720_422_10.yuv"              1280 720  8

#!/bin/bash
set -u
. notes/cells.sh
run(){ CELL=$1; SRC=$2; W=$3; H=$4; SH=$5
 for a in 0 2 3; do
   D=out/F/${CELL}_b0.5_a$a.dec.yuv
   [ -f "$D" ] || { echo "missing $D"; continue; }
   python3 notes/gridmap.py "$SRC" $D $W $H 422 10 8 renders/${CELL}_f8_field_a$a --sh $SH --grid 64
   python3 notes/phase.py "$SRC" $D $W $H 422 10 8 64
 done
}
run spot   "$ARMS/long/spotrobotL_1920x1080_422_10.yuv" 1920 1080 16
run dng720 "$ARMS/dng_1280x720_422_10.yuv"              1280 720  8

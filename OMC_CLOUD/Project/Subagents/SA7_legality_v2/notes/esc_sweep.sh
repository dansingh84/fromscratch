#!/bin/bash
set -u
N=${N:-12}
run(){ CELL=$1; SRC=$2; W=$3; H=$4; BPP=$5
 for k in 1 2 3 4; do
  T=out/E/${CELL}_b${BPP}_k$k
  OMC_SA7_K=$k nice -n 19 ptree/omc_enc -i "$SRC" -o $T.omc -w $W -h $H --fmt 422 --depth 10 \
     --bpp $BPP -n $N --recon $T.rec.yuv 2> $T.log
  rc=$?; rm -f $T.rec.yuv
  if [ $rc -ne 0 ]; then echo "FAIL $CELL k$k rc=$rc"; exit 1; fi
  echo "ok $CELL bpp$BPP k$k $(stat -c%s $T.omc) md5=$(md5sum < $T.omc | cut -c1-8)"
 done
}
mkdir -p out/E
. notes/cells.sh
run spot   "$ARMS/long/spotrobotL_1920x1080_422_10.yuv"     1920 1080 ${BPP:-0.5}
run vb     "$ARMS/long/volleyballgameL_1920x1080_422_10.yuv" 1920 1080 ${BPP:-0.5}
run gfx    "$ARMS/cf_gfx_448x256_422_10.yuv"                 448  256  ${BPP:-0.5}
run dng1080 "$ARMS/dng_1920x1080_422_10.yuv"                 1920 1080 ${BPP:-0.5}
run dng720 "$ARMS/dng_1280x720_422_10.yuv"                   1280 720  ${BPP:-0.5}

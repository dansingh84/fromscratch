#!/bin/bash
set -u
. notes/cells.sh
run(){ CELL=$1; SRC=$2; W=$3; H=$4
 for B in 0.5 1.0; do
  T=out/P/${CELL}_b${B}
  OMC_SA7P=1 nice -n 19 ptree3/omc_enc -i "$SRC" -o $T.p3.omc -w $W -h $H --fmt 422 --depth 10 --bpp $B -n 12 --recon $T.rec.yuv 2> $T.p3.log
  rc=$?; [ $rc -ne 0 ] && { echo "FAIL $CELL $B p3 rc=$rc"; exit 1; }
  python3 notes/debias.py $T.rec.yuv $T.dec.yuv 10; rm -f $T.rec.yuv
  nice -n 19 out/basebin/omc_enc -i "$SRC" -o $T.base.omc -w $W -h $H --fmt 422 --depth 10 --bpp $B -n 12 --recon $T.brec.yuv 2> $T.base.log
  rc=$?; [ $rc -ne 0 ] && { echo "FAIL $CELL $B base rc=$rc"; exit 1; }
  python3 notes/debias.py $T.brec.yuv $T.bdec.yuv 10; rm -f $T.brec.yuv
  OMC_SA7_K=2 nice -n 19 ptree/omc_enc -i "$SRC" -o /dev/null -w $W -h $H --fmt 422 --depth 10 --bpp $B -n 12 --recon $T.erec.yuv 2> $T.esc.log
  rc=$?; [ $rc -ne 0 ] && { echo "FAIL $CELL $B esc rc=$rc"; exit 1; }
  rm -f $T.erec.yuv
  echo "ok $CELL $B p3=$(stat -c%s $T.p3.omc) base=$(stat -c%s $T.base.omc)"
 done
}
run spot    "$ARMS/long/spotrobotL_1920x1080_422_10.yuv"      1920 1080
run vb      "$ARMS/long/volleyballgameL_1920x1080_422_10.yuv" 1920 1080
run gfx     "$ARMS/cf_gfx_448x256_422_10.yuv"                 448  256
run dng1080 "$ARMS/dng_1920x1080_422_10.yuv"                  1920 1080
run dng720  "$ARMS/dng_1280x720_422_10.yuv"                   1280 720

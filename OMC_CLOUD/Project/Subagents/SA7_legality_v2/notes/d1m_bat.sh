#!/bin/bash
set -u
. notes/cells.sh
run(){ C=$1; S=$2; W=$3; H=$4; SH=$5
 for B in 0.5 1.0; do
  for arm in 0 1; do
   T=out/DM/${C}_b${B}_a$arm
   OMC_D1M0=$arm nice -n 19 ptree5/omc_enc -i "$S" -o $T.omc -w $W -h $H --fmt 422 --depth 10 --bpp $B -n 12 --recon $T.rec.yuv 2> $T.log
   rc=$?; [ $rc -ne 0 ] && { echo "FAIL $C $B a$arm rc=$rc"; exit 1; }
   python3 notes/debias.py $T.rec.yuv $T.d.yuv 10; rm -f $T.rec.yuv
   if [ $H -eq 1080 ]; then python3 notes/crop.py $T.d.yuv $T.c.yuv 1920 1088 1080 12; mv $T.c.yuv $T.d.yuv; fi
   python3 ../shared_tools/planepsnr.py "$S" $T.d.yuv $W $H 422 10 ${C}_${B}_a$arm > $T.psnr
   python3 ../shared_tools/rowbias.py "$S" $T.d.yuv $W $H 422 10 8 > $T.rowbias 2>&1
   python3 ../shared_tools/replprofile_a3.py "$S" $T.d.yuv $W $H 422 10 8 $SH > $T.repl 2>&1
   python3 ../shared_tools/rowphase3_a3.py "$S" $T.d.yuv $W $H 422 10 8 $SH > $T.phase 2>&1
   python3 ../shared_tools/flatplane.py "$S" $T.d.yuv $W $H 8 --fmt 422 --depth 10 > $T.flat 2>&1
  done
  echo "ok $C $B $(stat -c%s out/DM/${C}_b${B}_a0.omc)/$(stat -c%s out/DM/${C}_b${B}_a1.omc)"
 done
}
run dng720  "$ARMS/dng_1280x720_422_10.yuv"              1280 720  8
run dng1080 "$ARMS/dng_1920x1080_422_10.yuv"             1920 1080 16
run spot    "$ARMS/long/spotrobotL_1920x1080_422_10.yuv" 1920 1080 16
run gfx     "$ARMS/cf_gfx_448x256_422_10.yuv"            448  256  8

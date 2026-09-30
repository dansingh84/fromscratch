#!/bin/bash
# SA7 step-1 granularity oracle: level-1 rung sweep with the constructive step ON.
# usage: sweep.sh CELLNAME SRC W H NF
set -u
CELL=$1; SRC=$2; W=$3; H=$4; NF=$5
E=otree/omc_enc; D=otree/omc_dec
for r in 0 1 2 3; do
  T=out/D/${CELL}_r$r
  OMC_I14_ARM=3 OMC_I14_R=$r OMC_LATT_STAT=1 nice -n 19 $E -i "$SRC" -o $T.omc \
     -w $W -h $H --fmt 422 --depth 10 --bpp 0.5 -n $NF --recon $T.rec.yuv 2> $T.enc.log
  rc=$?; if [ $rc -ne 0 ]; then echo "ENC FAIL $CELL r$r rc=$rc"; exit 1; fi
  rm -f $T.rec.yuv
  OMC_I14_ARM=3 OMC_I14_R=$r nice -n 19 $D -i $T.omc -o $T.dec.yuv 2> $T.dec.log
  rc=$?; if [ $rc -ne 0 ]; then echo "DEC FAIL $CELL r$r rc=$rc"; exit 1; fi
  python3 ../shared_tools/planepsnr.py "$SRC" $T.dec.yuv $W $H 422 10 ${CELL}_r$r > $T.psnr.txt
  rc=$?; if [ $rc -ne 0 ]; then echo "PSNR FAIL $CELL r$r"; exit 1; fi
  echo "ok $CELL r$r bytes=$(stat -c%s $T.omc) md5=$(md5sum < $T.omc)"
done

#!/bin/bash
set -u
CELL=$1; SRC=$2; W=$3; H=$4; BPP=$5; NF=${6:-12}
NCP=$(( W/64 + 2 )); SH=$( [ $W -gt 1280 ] && echo 16 || echo 8 )
BITS=$(python3 -c "print(int(round($BPP*$W*$SH)))")
F=$(python3 -c "print(3*$NCP*3/$BITS)")
ABPP=$(python3 -c "print(round($BPP*(1-$F),6))")
echo "== $CELL W=$W ncp=$NCP slice_bits=$BITS syntax=$(python3 -c "print(round(100*$F,2))")%  armed bpp=$ABPP"
for a in 0 1 2 3; do
  T=out/F/${CELL}_b${BPP}_a$a
  B=$BPP; [ $a -ne 0 ] && B=$ABPP
  OMC_SA7F=$a OMC_SA7F_G=${G:-2} nice -n 19 ptree/omc_enc -i "$SRC" -o $T.omc -w $W -h $H --fmt 422 \
      --depth 10 --bpp $B -n $NF --recon $T.rec.yuv 2> $T.log
  rc=$?; if [ $rc -ne 0 ]; then echo "FAIL $CELL a$a rc=$rc"; exit 1; fi
  python3 notes/debias.py $T.rec.yuv $T.dec.yuv 10 || exit 1
  rm -f $T.rec.yuv
  python3 ../shared_tools/planepsnr.py "$SRC" $T.dec.yuv $W $H 422 10 ${CELL}_a$a > $T.psnr.txt || exit 1
  for fr in 8 11; do python3 ../shared_tools/flatplane.py "$SRC" $T.dec.yuv $W $H $fr --fmt 422 --depth 10 >> $T.flat.txt 2>&1; done
  echo "  a$a bytes=$(stat -c%s $T.omc) $(grep -oE 'repaired in [0-9]+ passes' $T.log) $(grep -oE 'gamut: -?[0-9]+ committed' $T.log)"
done

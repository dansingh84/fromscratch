#!/bin/bash
# [SA7-R1 S5.253] the real bar: PICTURE locks at g2, STREAM at g3..g8.
# usage: r1_chain.sh <name> <arm.yuv> <W> <H> <fmt> <depth> <bpp> <outdir> [extra env]
set -u
N=$1; A=$2; W=$3; H=$4; F=$5; D=$6; R=$7; O=$8; shift 8
E=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/rtree1
mkdir -p "$O"
enc(){ timeout 3600 env "$@" $E/omc_enc -i "$IN" -o "$OUT" -w $W -h $H --fmt $F --depth $D --bpp $R -n 1 --gamut-strict 0 >/dev/null 2>&1; }
IN=$A; OUT=$O/$N.g1; enc "$@" ; RC=$?; [ $RC -ne 0 ] && { echo "$N: g1 FAILED rc=$RC"; exit 1; }
$E/omc_dec -i $O/$N.g1 -o $O/$N.p1.yuv >/dev/null 2>&1 || { echo "$N: dec1 FAILED"; exit 1; }
PREVS=$O/$N.g1; PREVP=$O/$N.p1.yuv; PICBAR=""; STREAM=""
for G in 2 3 4 5 6 7 8; do
  IN=$PREVP; OUT=$O/$N.g$G; enc "$@"; RC=$?
  [ $RC -ne 0 ] && { echo "$N: g$G enc FAILED rc=$RC"; exit 1; }
  $E/omc_dec -i $O/$N.g$G -o $O/$N.p$G.yuv >/dev/null 2>&1 || { echo "$N: dec$G FAILED"; exit 1; }
  if [ $G -eq 2 ]; then
    DIFF=$(cmp -l $PREVP $O/$N.p$G.yuv 2>/dev/null | wc -l); PICBAR=$DIFF
  fi
  if [ $G -ge 3 ]; then
    if cmp -s $PREVS $O/$N.g$G; then STREAM="$STREAM g$((G-1))=g$G:OK"; else STREAM="$STREAM g$((G-1))=g$G:DIFF"; fi
  fi
  rm -f $PREVP; PREVP=$O/$N.p$G.yuv; PREVS=$O/$N.g$G
done
echo "$N: picture_moved_at_g2=$PICBAR |$STREAM"
rm -f $O/$N.p*.yuv

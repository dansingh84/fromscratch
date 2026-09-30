#!/bin/bash
# [SA11 T-B] shipped defaults (OMC_R1 unset, --gamut-strict at its default), 8 frames.
set -u
E=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/rtree4
N=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/notes
T=$1; SRC=$2; W=$3; H=$4; R=$5; O=$6; X=${7:-}
cd "$O"
unset OMC_R1 OMC_R1_REUSE OMC_R1_STAT
env OMC_U_SLSTAT=1 "$E/omc_enc" -i "$SRC" -o $T.omc -w $W -h $H --fmt 422 --depth 10 --bpp $R -n 8 >/dev/null 2>$T.err; rc=$?
[ $rc -ne 0 ] && { echo "TB $T ENC rc=$rc"; exit 1; }
"$E/omc_dec" -i $T.omc -o $T.dec.yuv >/dev/null 2>&1 || { echo "TB $T DEC FAILED"; rm -f $T.dec.yuv; exit 1; }
echo "=== $T bytes=$(stat -c %s $T.omc) gamut default, OMC_R1 unset"
python3 $N/tb_an.py "$SRC" $T.dec.yuv $W $H 8 $T.err $X
rm -f $T.dec.yuv

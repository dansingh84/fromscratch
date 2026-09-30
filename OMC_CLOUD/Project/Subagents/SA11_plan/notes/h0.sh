#!/bin/bash
# [SA11 H0] usage: h0.sh tag src W H bpp outdir "extra env" "extra enc args"
set -u
E=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/rtree4
N=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/notes
T=$1; SRC=$2; W=$3; H=$4; R=$5; O=$6; XE=${7:-}; XA=${8:-}
mkdir -p "$O/$T"; cd "$O/$T"
unset OMC_R1 OMC_R1_REUSE OMC_R1_STAT
env OMC_U_SLSTAT=1 OMC_H0_DUMP=5 $XE "$E/omc_enc" -i "$SRC" -o $T.omc -w $W -h $H --fmt 422 --depth 10 --bpp $R -n 8 $XA >/dev/null 2>$T.err; rc=$?
[ $rc -ne 0 ] && { echo "H0 $T ENC rc=$rc"; exit 1; }
"$E/omc_dec" -i $T.omc -o $T.dec.yuv >/dev/null 2>&1 || { echo "H0 $T DEC FAILED"; rm -f $T.dec.yuv; exit 1; }
echo "=== $T env[$XE] args[$XA] bytes=$(stat -c %s $T.omc)"
python3 $N/tb_an.py "$SRC" $T.dec.yuv $W $H 8 $T.err
python3 $N/h0_stage.py . $T.dec.yuv $W $H 5
rm -f $T.dec.yuv

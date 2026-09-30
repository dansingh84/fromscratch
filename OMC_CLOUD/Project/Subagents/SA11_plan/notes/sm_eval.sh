#!/bin/bash
# [SA11 SM] smudge evaluation of one decode with the owner's tools.
# usage: sm_eval.sh tag SRC DEC W H sh first last renderframes outdir
set -u
T=$1; SRC=$2; DEC=$3; W=$4; H=$5; SH=$6; F0=$7; F1=$8; RF=$9; O=${10}
ST=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools
LM=/home/user/fromscratch/OMC_CLOUD/Project/.work/v537/harness/levelmap.py
GM=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/notes/gridmap.py
mkdir -p "$O/renders" "$O/sg"
for f in $(seq $F0 $F1); do
  for cfg in "6 0.4" "12 0.5"; do set -- $cfg
    echo "== $T f$f thr $1 dens $2"
    python3 $ST/smudgegroups.py "$SRC" "$DEC" $W $H $f "$O/sg/${T}_f${f}_t$1" --sh $SH --thr $1 --dens $2 2>&1 | grep -E '^(Y|Cb|Cr):'
  done
done
for f in $RF; do
  python3 $LM "$SRC" "$DEC" $W $H $f "$O/renders/${T}_f${f}_level.png" --sh $SH --plane all >/dev/null 2>&1 || echo "levelmap FAILED $T $f"
  python3 $GM "$SRC" "$DEC" $W $H 422 10 $f "$O/renders/${T}_f${f}_grid" --sh $SH --grid 64 >/dev/null 2>&1 || echo "gridmap FAILED $T $f"
done

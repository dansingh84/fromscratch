#!/bin/bash
# two-pass static table training on the 5 disjoint clips, 5 processes in parallel, 4 frames x 2 rates each
set -e
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model
OUT=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/out/tables; mkdir -p $OUT
PASS=$1   # p1 or p2
INIT=""; [ "$PASS" = p2 ] && INIT=$OUT/tables_p1.pkl; [ "$PASS" = p3 ] && INIT=$OUT/tables_p2.pkl
for i in 0 1 2 3 4; do nice -n 19 python3 train.py clip $i $INIT 4 > $OUT/log_${PASS}_$i.txt 2>&1 & done
wait
python3 train.py merge $PASS
echo "TRAIN_${PASS}_DONE"

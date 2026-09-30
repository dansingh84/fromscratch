#!/bin/bash
# detached master queue (SA16, 00:35 2026-09-29): waits for the jobs already running, then the 10 remaining efficiency
# points (6 in parallel), then sequence tests and rails. Exit codes -> out/eval/queue_status.txt. tables_p2 everywhere.
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model
OUT=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/out; TAB=$OUT/tables/tables_p2.pkl
echo "QUEUE_ALL start $(date)" >> $OUT/eval/queue_status.txt
while pgrep -f "python3 (evalcell|t_hh|t_seq|train).py" > /dev/null; do sleep 60; done
echo "PHASE0 (pre-existing jobs) done $(date)" >> $OUT/eval/queue_status.txt
python3 train.py merge p3 >> $OUT/train_p3.log 2>&1; echo "MERGE p3 exit $?" >> $OUT/eval/queue_status.txt
rm -f $OUT/eval/dng720_*.yuv
./run_queue.sh $TAB 6 dng1080:0.5 dng1080:1.0 spot:0.5 spot:1.0 floor:0.5 floor:1.0 hwy:0.5 hwy:1.0 volley:0.5 volley:1.0
echo "PHASE1 (10 points) done $(date)" >> $OUT/eval/queue_status.txt
export TAB
( nice -n 19 python3 t_seq.py mixed dng720 0.5 > $OUT/seq/mixed.log 2>&1; echo "SEQ mixed exit $?" >> $OUT/eval/queue_status.txt ) &
( nice -n 19 python3 t_seq.py gen dng720 0.5 > $OUT/seq/gen.log 2>&1; echo "SEQ gen exit $?" >> $OUT/eval/queue_status.txt ) &
( nice -n 19 python3 t_seq.py loss dng720 0.5 > $OUT/seq/loss.log 2>&1; echo "SEQ loss exit $?" >> $OUT/eval/queue_status.txt ) &
( nice -n 19 python3 t_seq.py join dng720 0.5 > $OUT/seq/join.log 2>&1; echo "SEQ join exit $?" >> $OUT/eval/queue_status.txt ) &
( nice -n 19 python3 t_rails.py > $OUT/seq/rails.log 2>&1; echo "RAILS exit $?" >> $OUT/eval/queue_status.txt ) &
( nice -n 19 python3 t_seq.py gen floor 0.5 > $OUT/seq/gen_floor.log 2>&1; echo "SEQ gen floor exit $?" >> $OUT/eval/queue_status.txt ) &
wait
echo "QUEUE_ALL done $(date)" >> $OUT/eval/queue_status.txt

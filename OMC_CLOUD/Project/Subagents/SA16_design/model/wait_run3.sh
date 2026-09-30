#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model
OUT=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/out
until grep -q TRAIN_p3_DONE $OUT/train_p3.log; do sleep 30; done
rm -f $OUT/eval/dng720_0.5.* $OUT/eval/dng720_1.0.* $OUT/eval/spot_0.5.*
NF=12 ./run_queue.sh $OUT/tables/tables_p3.pkl 2 dng720:0.5 dng720:1.0 &
NF=8 ./run_queue.sh $OUT/tables/tables_p3.pkl 1 spot:0.5 &
wait; echo RUN3_DONE >> $OUT/eval/queue_status.txt

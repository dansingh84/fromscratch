#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for cm in 1 0.85; do for c in cine_4k_A006 gfx444_F003C012 cine_A005C021; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 4 ]; do sleep 60; done
  RHO=0.42 RHOK=0.5 nice -n 5 python3 bench/rcl_s16.py $c $cm S16 > out/rcl_s16/rk42_cm${cm}_$c.log 2>&1 < /dev/null &
  sleep 5
done; done; wait
SP=/tmp/claude-0/-home-user-fromscratch/ca3365f6-68f7-5957-a3a2-a3df5f0ee7ba/scratchpad
for f in out/rcl_s16/rk42_cm*.log; do b=$(basename $f .log); sed "s/_S16 /_S16$b /" $f > $SP/$b.log; done
python3 bench/intra_vs_today.py $SP/rk42_cm*.log > out/rk42_vs_today_train.txt 2>&1

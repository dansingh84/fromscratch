#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for cm in 1 0.85 0.7; do for c in cine_4k_A006 cine_A005C021 gfx444_F003C012; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 4 ]; do sleep 20; done
  nice -n 19 python3 bench/rcl_s16.py $c $cm S16 > out/rcl_s16/fit_${c}_cm$cm.log 2>&1 < /dev/null &
  sleep 5
done; done; wait

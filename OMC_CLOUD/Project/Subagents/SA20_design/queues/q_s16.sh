#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for cm in 0.85 0.7; do for c in cine_A005C031 gfx444_B001C001 prores_sample; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 4 ]; do sleep 20; done
  ONLY=S16 nice -n 19 python3 bench/rcl_sc.py $c $cm > out/rcl_tab/sc_${c}_cm$cm.log 2>&1 < /dev/null &
  sleep 5
done; done; wait

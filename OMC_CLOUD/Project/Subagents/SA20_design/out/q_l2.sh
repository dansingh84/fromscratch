#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for c in cine_A005C031 gfx444_B001C001 prores_sample; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 20; done
  nice -n 19 python3 bench/rcl_s16.py $c 1 S16l2 > out/rcl_s16/lane_${c}_S16l2.log 2>&1 < /dev/null &
  sleep 5
done; wait

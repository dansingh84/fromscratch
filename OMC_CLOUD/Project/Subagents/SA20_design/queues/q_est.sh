#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
while ps -eo args | grep -q "^python3 bench/rcl_s16.py cine_A005C031 1 S16$"; do sleep 30; done
for c in cine_A005C031 gfx444_B001C001 prores_sample; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 20; done
  EST=1 nice -n 19 python3 bench/rcl_s16.py $c 1 S16 > out/rcl_s16/est_$c.log 2>&1 < /dev/null &
  sleep 5
done; wait

#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
while kill -0 15700 2>/dev/null; do sleep 30; done
for arm in cm1 cm1_cl; do for c in cine_A005C031 gfx444_B001C001 prores_sample; do
  while [ $(pgrep -fc "bench/rcl_") -ge 3 ]; do sleep 20; done
  nice -n 19 python3 bench/rcl_seq.py $c $arm > out/rcl_seq/${c}_$arm.log 2>&1 < /dev/null &
  sleep 2
done; done; wait

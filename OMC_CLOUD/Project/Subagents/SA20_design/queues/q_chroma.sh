#!/bin/bash
# queue: chroma allocation + chroma-from-luma arms, real code lengths, intra f0; max 3 in parallel
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
while pgrep -f rcl_intra.py >/dev/null; do sleep 30; done
mkdir -p out/rcl_fi
for arm in cm1 cm0.7 cm0.5 cm1_cl cm0.7_cl; do for c in cine_A005C031 gfx444_B001C001 prores_sample; do
  while [ $(pgrep -fc "rcl_fi.py") -ge 3 ]; do sleep 20; done
  nice -n 19 python3 bench/rcl_fi.py $c $arm > out/rcl_fi/${c}_$arm.log 2>&1 < /dev/null &
  sleep 2
done; done; wait

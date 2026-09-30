#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for arm in cm1 cm0.85; do for c in cine_A005C031 gfx444_B001C001 prores_sample; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 4 ]; do sleep 20; done
  nice -n 19 python3 bench/rcl_ctx.py $c $arm > out/rcl_ctx/${c}_$arm.log 2>&1 < /dev/null &
  sleep 30
done; done; wait
python3 bench/intra_vs_today.py out/rcl_ctx/*.log > out/rcl_ctx/intra_vs_today.txt 2>&1

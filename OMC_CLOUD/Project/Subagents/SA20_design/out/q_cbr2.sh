#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for arm in cm1_zb2_hy0.75 cm1_zb2; do nice -n 19 python3 bench/rcl_cbr.py train $arm > out/rcl_cbr/train_$arm.log 2>&1 < /dev/null & done; wait
for arm in cm1_zb2_hy0.75 cm1_zb2; do for c in cine_frozen cine_A005C031 gfx444_B001C001 prores_sample; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 4 ]; do sleep 20; done
  nice -n 19 python3 bench/rcl_cbr.py $c $arm > out/rcl_cbr/${c}_$arm.log 2>&1 < /dev/null &
  sleep 5
done; done; wait

#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
ARM=cm1_zb2_hy0.75_sg_s16
nice -n 19 python3 bench/rcl_cbr.py train $ARM > out/rcl_cbr/train_$ARM.log 2>&1 < /dev/null
for c in cine_A005C031 gfx444_B001C001 prores_sample; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 4 ]; do sleep 20; done
  nice -n 19 python3 bench/rcl_cbr.py $c $ARM > out/rcl_cbr/${c}_$ARM.log 2>&1 < /dev/null &
  sleep 5
done; wait

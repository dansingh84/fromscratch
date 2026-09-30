#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for arm in cm1_lg1 cm0.85_lg1 cm1_lg2; do for c in cine_A005C031 gfx444_B001C001 prores_sample; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 4 ]; do sleep 20; done
  nice -n 19 python3 bench/rcl_fi.py $c $arm > out/rcl_fi/${c}_$arm.log 2>&1 < /dev/null &
  sleep 30
done; done; wait
python3 bench/intra_vs_today.py out/rcl_fi/*_lg*.log out/rcl_fi/*_cm1.log > out/rcl_fi/lg_vs_today.txt 2>&1

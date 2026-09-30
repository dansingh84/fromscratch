#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for cm in 0.85 0.7; do for c in cine_4k_A006 gfx444_F003C012 cine_A005C021; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 6 ]; do sleep 60; done
  RHO=0.42 nice -n 8 python3 bench/rcl_s16.py $c $cm S16 > out/rcl_s16/cm${cm}_rho0.42_$c.log 2>&1 < /dev/null &
  sleep 5
done; done; wait
cd out/rcl_s16; for f in cm0.*_rho0.42_*.log; do sed -i "s/_S16 /_S16r42 /" $f; done; cd ../..
python3 bench/intra_vs_today.py out/rcl_s16/cm0.*_rho0.42_*.log > out/cm42_vs_today_train.txt 2>&1

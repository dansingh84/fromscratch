#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
while [ $(ps -eo args | grep -c "^python3 bench/rcl_s16") -ge 6 ]; do sleep 60; done
for r in 0.42 0.5; do for c in gfx444_F003C012 cine_A005C021; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 6 ]; do sleep 60; done
  RHO=$r nice -n 5 python3 bench/rcl_s16.py $c 1 S16 > out/rcl_s16/rho${r}_$c.log 2>&1 < /dev/null &
  sleep 5
done; done; wait
for r in 0.42 0.5; do for c in cine_4k_A006 gfx444_F003C012 cine_A005C021; do for R in 1.0 2.0; do
  RHO=$r python3 bench/intra_eval.py $c $R out/rcl_s16/rho${r}_$c.log; done; done; done > out/ieval_rho.txt 2>&1

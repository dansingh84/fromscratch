#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for c in cine_npan0.5s2 cine_pan0.25 cine_pan1.0; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 30; done
  NF=10 RATES=0.5,2.0 nice -n 6 python3 bench/rcl_cbr.py $c cm1_zb2_chp_s16 > out/rcl_cbr/ctl_$c.log 2>&1 < /dev/null &
  sleep 5
done; wait

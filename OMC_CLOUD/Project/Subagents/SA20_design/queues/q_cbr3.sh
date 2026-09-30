#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
until [ -f out/rcl_cbr/tables_cm1_zb2_hy0.75.pkl ] && [ -f out/rcl_cbr/tables_cm1_zb2.pkl ]; do sleep 30; done
cp out/rcl_cbr/tables_cm1_zb2_hy0.75.pkl out/rcl_cbr/tables_cm1_zb2_hy0.75_sg.pkl
for c in cine_frozen10 cine_pan0.5 cine_pan0.25 cine_pan1.0; do for arm in cm1_zb2_hy0.75_sg cm1_zb2; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 4 ]; do sleep 20; done
  NF=10 RATES=0.5,1.0 nice -n 19 python3 bench/rcl_cbr.py $c $arm > out/rcl_cbr/n10_${c}_$arm.log 2>&1 < /dev/null &
  sleep 5
done; done; wait

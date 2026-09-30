#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for k in 2 3 1.5 2.5; do A=cm1_zb2_hy0.75_rs_ramp1_sl_gn${k}_chp_s16; cp out/rcl_cbr/tables_cm1_zb2_hy0.75_sg_s16.pkl out/rcl_cbr/tables_$A.pkl
  for c in cine_nfrozen2 cine_nfrozen3 cine_npan0.5s2 cine_pan0.25; do
    while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 30; done
    NF=10 RATES=0.5,2.0 nice -n 4 python3 bench/rcl_cbr.py $c $A > out/rcl_cbr/gn${k}_$c.log 2>&1 < /dev/null &
    sleep 5
  done; done; wait

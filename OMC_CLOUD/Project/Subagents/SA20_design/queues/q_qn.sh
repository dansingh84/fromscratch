#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
while ps -eo args | grep -q "^bash out/q_gn.sh"; do sleep 60; done
for c in 2 3; do A=cm1_zb2_hy0.75_rs_ramp1_sl_gn3_qn${c}_chp_s16; cp out/rcl_cbr/tables_cm1_zb2_hy0.75_sg_s16.pkl out/rcl_cbr/tables_$A.pkl
  for clip in cine_nfrozen2 cine_nfrozen3 cine_npan0.5s2 cine_pan0.25 cine_frozen10; do
    while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 30; done
    NF=10 RATES=0.5,2.0 nice -n 4 python3 bench/rcl_cbr.py $clip $A > out/rcl_cbr/qn${c}_$clip.log 2>&1 < /dev/null &
    sleep 5
  done; done; wait

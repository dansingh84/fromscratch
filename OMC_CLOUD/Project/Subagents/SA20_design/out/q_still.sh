#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for c in cine_frozen10 cine_nfrozen2 cine_nfrozen1 cine_nfrozen3 cine_npan0.5s2 cine_pan0.5; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 20; done
  NF=10 RATES=0.5,1.0,2.5,4.0 nice -n 10 python3 bench/rcl_cbr.py $c cm1_zb2_hy0.75_sg_keep_rs_ng_cu0 > out/rcl_cbr/still_${c}.log 2>&1 < /dev/null &
  sleep 5
done; wait

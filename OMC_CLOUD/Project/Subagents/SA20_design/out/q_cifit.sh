#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for ci in 0.8 0.65 1; do for c in cine_4k_A006 cine_A005C021 gfx444_F003C012; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 30; done
  NF=2 RATES=0.5,1.0,2.0,4.0 LOO=1 nice -n 19 python3 bench/rcl_cbr.py $c cm1_ci${ci}_zb2_hy0.75_sg_keep_rs_ng_cu0_s16 > out/rcl_cbr/cifit_${c}_ci$ci.log 2>&1 < /dev/null &
  sleep 5
done; done; wait

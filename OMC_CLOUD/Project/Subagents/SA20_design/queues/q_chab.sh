#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for a in cm1_zb2_hy0.75_sg_keep_rs_ng_cu0_s16_chp cm1_zb2_hy0.75_sg_keep_rs_ng_cu0_s16 cm1_zb2_hy0.75_sg_keep_rs_ng_cu0_s16_pp cm1_zb2_hy0.75_sg_keep_rs_ng_cu0_s16_chp_pp; do for c in cine_A005C031 prores_sample; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 30; done
  RATES=0.5,1.0,2.0 nice -n 12 python3 bench/rcl_cbr.py $c $a > out/rcl_cbr/chab_${c}_$a.log 2>&1 < /dev/null &
  sleep 5
done; done; wait

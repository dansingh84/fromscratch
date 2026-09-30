#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for c in gfx444_B001C001 cine_A005C031; do for a in cm1_zb2_hy0.75_sg_keep_rs_ng_bz_ramp1_rg_rr_mf_acc_g2_sh_win_chp_s16 cm1_zb2_chp_s16 cm1_zb2_hy0.75_rs_chp_s16; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 30; done
  RATES=1.0 nice -n 4 python3 bench/rcl_cbr.py $c $a > out/rcl_cbr/grain_${c}_${a:0:40}.log 2>&1 < /dev/null &
  sleep 5
done; done; wait

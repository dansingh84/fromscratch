#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
run() { while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 30; done; env $1 nice -n 6 python3 bench/rcl_cbr.py $2 $3 > out/rcl_cbr/rg2_$2_$4.log 2>&1 < /dev/null & sleep 5; }
for a in A C; do arm=$([ $a = A ] && echo cm1_zb2_hy0.75_sg_keep_rs_ng_bz_ramp1_rg_mf_dr_chp_s16 || echo cm1_zb2_hy0.75_sg_keep_rs_ng_bz_ramp1_cua_dr_chp_s16)
  run RATES=1.0,2.0 gfx444_B001C001 $arm $a
  run RATES=0.5,1.0 cine_A005C031 $arm $a
  run "NF=10 RATES=0.5,1.0" cine_nfrozen2 $arm $a
  run "NF=10 RATES=0.5" cine_npan0.5s2 $arm $a
done; wait

#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
run() { while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 30; done; env $1 nice -n 4 python3 bench/rcl_cbr.py $2 cm1_zb2_hy0.75_sg_keep_rs_ng_bz_ramp1_rg_mf_acc_g2_sh_chp_s16 > out/rcl_cbr/acc3_$2.log 2>&1 < /dev/null & sleep 5; }
run "NF=10 RATES=0.5,1.0" cine_nfrozen2
run "NF=10 RATES=0.5,2.0" cine_npan0.5s2
run "NF=10 RATES=0.5" cine_pan0.25
run "NF=10 RATES=0.5" cine_pan1.0
run "NF=10 RATES=0.5" cine_frozen10
run "RATES=1.0,2.0" gfx444_B001C001
wait

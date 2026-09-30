#!/bin/bash
# G77: spatial sigma-hat (sn) and refinement rate margin (rm0.9), plus the no-hold control rerun with temporal metrics
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
while pgrep -f q_clean.sh > /dev/null; do sleep 30; done
run() { NF=10 RATES=0.5,2.0 python3 bench/rcl_cbr.py $2 $3 > out/rcl_cbr/$1_$2.log 2>&1; }
B=cm1_zb2_hy0.75_rs_ramp1_sl_gn3_qn3
for c in cine_pan0.25 cine_npan0.5s2 cine_nfrozen2 cine_nfrozen3 cine_frozen10; do
  run sn $c ${B}_sn_chp_s16 & run snrm $c ${B}_sn_rm0.9_chp_s16 & wait
done
for c in cine_pan0.25 cine_npan0.5s2 cine_nfrozen2; do run ctl2 $c cm1_zb2_chp_s16 & done; wait

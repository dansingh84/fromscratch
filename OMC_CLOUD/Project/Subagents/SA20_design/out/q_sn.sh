#!/bin/bash
# G77: sigma-hat variants (sn spatial, snm = min(spatial, temporal)) x refinement margin (rm0.85, rm0.9, rm0 = never refine
# after the ramp), and the no-hold control rerun with temporal metrics. Frames 0-1 are already exempt from the slew.
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
run() { NF=10 RATES=0.5,2.0 python3 bench/rcl_cbr.py $2 $3 > out/rcl_cbr/$1_$2.log 2>&1; }
B=cm1_zb2_hy0.75_rs_ramp1_sl_gn3_qn3
for c in cine_pan0.25 cine_nfrozen2 cine_npan0.5s2 cine_nfrozen3 cine_frozen10; do
  run snm85 $c ${B}_snm_rm0.85_chp_s16 & run snm0 $c ${B}_snm_rm0_chp_s16 & run sn85 $c ${B}_sn_rm0.85_chp_s16 & wait
done
for c in cine_pan0.25 cine_npan0.5s2 cine_nfrozen2; do run ctl2 $c cm1_zb2_chp_s16 & done; wait

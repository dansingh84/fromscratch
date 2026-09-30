#!/bin/bash
# G76: keep the qn3 decodes of the noisy frozen clips and measure PSNR against the clean picture per frame
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
for c in cine_nfrozen2 cine_nfrozen3; do
  KEEPYUV=1 NF=10 RATES=0.5,2.0 python3 bench/rcl_cbr.py $c cm1_zb2_hy0.75_rs_ramp1_sl_gn3_qn3_chp_s16 > out/rcl_cbr/clean_$c.log 2>&1 &
done; wait
python3 tools/diag_clean.py $A/cine_frozen10_1280x720_422_10.yuv out/rcl_cbr/cine_nfrozen{2,3}_cm1_zb2_hy0.75_rs_ramp1_sl_gn3_qn3_chp_s16_{0.5,2.0}.yuv $A/cine_nfrozen{2,3}_1280x720_422_10.yuv > out/rcl_cbr/clean_psnr.txt
rm -f out/rcl_cbr/cine_nfrozen*_qn3_chp_s16_*.yuv

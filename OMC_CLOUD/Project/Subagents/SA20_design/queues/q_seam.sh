#!/bin/bash
# G79: seam cause, cine_A005C031 (3 frames) at 0.5/1.0/2.0: base candidate vs +ob (overlapped MC) vs +sm (continuous
# per-sample parameter fields) vs both; visual_check against today.
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms; T=/home/user/fromscratch/OMC_CLOUD/scratch/today; O=out/rcl_cbr; c=cine_A005C031
for ext in ob sm ob_sm; do
  ARM=cm1_zb2_hy0.75_rs_ramp1_sl_gn3_qn3_${ext}_chp_s16
  KEEPYUV=1 RHO=0.42 RHOK=0.5 NF=3 RATES=0.5,1.0,2.0 python3 bench/rcl_cbr.py $c $ARM > out/vis/seam_${ext}.log 2>&1
  for r in 0.5 1.0 2.0; do
    python3 tools/visual_check.py $A/${c}_1280x720_422_10.yuv $O/${c}_${ARM}_RHO0.42_RHOK0.5_$r.yuv $T/${c}_1280x720_b$r.d.yuv 3 > out/vis/seam_${ext}_$r.txt 2>&1
  done
  rm -f $O/${c}_${ARM}_RHO0.42_RHOK0.5_*.yuv
done

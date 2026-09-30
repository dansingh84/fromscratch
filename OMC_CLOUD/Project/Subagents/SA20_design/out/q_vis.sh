#!/bin/bash
# G78: owner visual checks (smudge groups, lines, grid phase, seams) on the current full candidate vs today, all owner
# footage, all 7 rates, every frame. Candidate = still rule gn3 qn3 + leaf rho 0.42 + kept rounding 0.5.
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms; T=/home/user/fromscratch/OMC_CLOUD/scratch/today
ARM=cm1_zb2_hy0.75_rs_ramp1_sl_gn3_qn3_chp_s16; O=out/rcl_cbr; mkdir -p out/vis
for c in cine_A005C031 gfx444_B001C001 prores_sample cine_4k_A006 cine_A005C021 gfx444_F003C012; do
  case $c in cine_4k_A006|cine_A005C021) nf=2; loo=1;; gfx444_F003C012) nf=3; loo=1;; *) nf=3; loo=0;; esac
  LOO=$loo KEEPYUV=1 RHO=0.42 RHOK=0.5 NF=$nf python3 bench/rcl_cbr.py $c $ARM > out/vis/run_$c.log 2>&1
  for r in 0.5 1.0 1.5 2.0 2.5 3.0 4.0; do
    python3 tools/visual_check.py $A/${c}_1280x720_422_10.yuv $O/${c}_${ARM}_RHO0.42_RHOK0.5_$r.yuv $T/${c}_1280x720_b$r.d.yuv $nf > out/vis/${c}_$r.txt 2>&1
  done
  rm -f $O/${c}_${ARM}_RHO0.42_RHOK0.5_*.yuv
done

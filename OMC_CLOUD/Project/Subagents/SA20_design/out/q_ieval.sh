#!/bin/bash
# evaluates finished intra arms: waits until each log has >= 12 rows and no writer is alive
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for arm in f0.6 f0.5 rk0.5; do for c in cine_4k_A006 gfx444_F003C012 cine_A005C021; do
  L=out/rcl_s16/${arm}_$c.log
  until [ $(grep -c Q= $L 2>/dev/null) -ge 12 ]; do sleep 60; done
  case $arm in f*) E="F=${arm#f}";; rk*) E="RHOK=${arm#rk}";; esac
  for r in 1.0 2.0; do env $E python3 bench/intra_eval.py $c $r $L; done
done; done > out/ieval_arms.txt 2>&1

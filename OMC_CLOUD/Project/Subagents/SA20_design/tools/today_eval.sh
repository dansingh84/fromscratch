#!/bin/bash
# today_eval.sh — regenerates out/today_eval.txt (today's v537 decodes scored per frame; format read by the bench).
# Needs tools/run_today.sh (test clips, 720p + 1080p) run first with RATES="0.5 1.0 1.5 2.0 2.5 3.0 4.0".
R=/home/user/fromscratch/OMC_CLOUD; B=$(dirname "$0")/../bench; mkdir -p $(dirname "$0")/../out
for c in cine_A005C031 gfx444_B001C001 prores_sample; do for g in 1280x720 1920x1080; do for b in 0.5 1.0 1.5 2.0 2.5 3.0 4.0; do
  W=${g%x*}; H=${g#*x}; D=$R/scratch/today/${c}_${g}_b$b.d.yuv; [ -s $D ] || continue
  python3 $B/eval20.py $R/Project/.work/arms/${c}_${g}_422_10.yuv $D $W $H 422 10 ${c}_${g}_b$b | head -1
done; done; done > $(dirname "$0")/../out/today_eval.txt

#!/bin/bash
# today's codec (v537, read-only) on the new test cells: 720p + 1080p, 0.5/1.0 bpp, 3 frames
V=/home/user/fromscratch/OMC_CLOUD/Project/.work/v537; A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
O=/home/user/fromscratch/OMC_CLOUD/scratch/today; T=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools
for c in ${CLIPS:-cine_A005C031 gfx444_B001C001 prores_sample}; do for g in ${GEOMS:-1280x720 1920x1080}; do for b in ${RATES:-0.5 1.0}; do
 W=${g%x*}; H=${g#*x}; S=$A/${c}_${g}_422_10.yuv; N=$O/${c}_${g}_b$b
 $V/omc_enc -i $S -o $N.omc -w $W -h $H --bpp $b > $N.enc.log 2>&1; ec=$?
 $V/omc_dec -i $N.omc -o $N.d.yuv > $N.dec.log 2>&1
 neg=$(bash $T/negscore.sh $S $N.d.yuv $W $H 422 10 3)
 echo "$c $g $b enc_exit=$ec bytes=$(stat -c %s $N.omc) NEG3=$neg"
done; done; done

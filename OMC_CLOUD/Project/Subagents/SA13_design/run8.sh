#!/bin/bash
# T8 battery: today's real decodes, then BSC-1 inter model at two steps per cell.
A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms; DM=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/out/DM
SCR=/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA13_design
declare -A SRC=([dng720]="$A/dng_1280x720_422_10.yuv 1280 720" [dng1080]="$A/dng_1920x1080_422_10.yuv 1920 1080" [spot]="$A/long/spotrobotL_1920x1080_422_10.yuv 1920 1080" [gfx]="$A/cf_gfx_448x256_422_10.yuv 448 256")
declare -A SH=([dng720]=8 [dng1080]=16 [spot]=16 [gfx]=16)
for c in dng720 dng1080 spot gfx; do for b in 0.5 1.0; do
  set -- ${SRC[$c]}; python3 eval_dec.py $1 $DM/${c}_b${b}_a0.d.yuv $2 $3 12 ${SH[$c]} TODAY_${c}_b$b || echo FAIL $c $b
done; done
for c in dng720 dng1080 spot gfx; do for D in $DSET; do for S in ${SLIST:-${SH[$c]}}; do
  set -- ${SRC[$c]}; o=$SCR/b8_${c}_S${S}_D$D.yuv
  nice -n 19 python3 t8_inter.py $1 $2 $3 422 12 BSC_${c}_S${S}_D$D $S $D --out $o || echo FAIL $c
  python3 eval_dec.py $1 $o $2 $3 12 ${SH[$c]} BSC_${c}_S${S}_D$D || echo FAIL eval $c
  rm -f $o
done; done; done

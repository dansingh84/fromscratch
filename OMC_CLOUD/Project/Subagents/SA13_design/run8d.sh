#!/bin/bash
A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
SCR=/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA13_design
run() { o=$SCR/b8d_$1_$5_$6.yuv
  nice -n 19 python3 t8_inter.py $2 $3 $4 422 12 V2_$1_S$5_D$6 $5 $6 --dzi 1.25 --lam 1 --out $o || echo FAIL $1
  python3 eval_dec.py $2 $o $3 $4 12 $7 V2_$1_S$5_D$6 || echo FAIL eval; rm -f $o; }
for D in 36 72; do run dng720 $A/dng_1280x720_422_10.yuv 1280 720 8 $D 8; done
for D in 36 72; do run dng1080 $A/dng_1920x1080_422_10.yuv 1920 1080 8 $D 16; done
for D in 24 48; do run spot $A/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 8 $D 16; done
for D in 36 72; do run gfx $A/cf_gfx_448x256_422_10.yuv 448 256 8 $D 16; done

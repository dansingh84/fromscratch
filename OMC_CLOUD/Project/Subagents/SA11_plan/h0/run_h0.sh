#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/h0
H=../notes/h0.sh; P=$PWD
bash $H gfx_zg0 $P/still_gfx.yuv 448 256 0.5 $P "OMC_H0_ZERO=1" "--gamut-strict 0" > gfx_zg0.txt 2>&1
bash $H dng720_z $P/still_dng720.yuv 1280 720 0.5 $P "OMC_H0_ZERO=1" "" > dng720_z.txt 2>&1
bash $H dng720_zg0 $P/still_dng720.yuv 1280 720 0.5 $P "OMC_H0_ZERO=1" "--gamut-strict 0" > dng720_zg0.txt 2>&1
bash $H spot10_z $P/still_spot.yuv 1920 1080 1.0 $P "OMC_H0_ZERO=1" "" > spot10_z.txt 2>&1
bash $H spot10_zg0 $P/still_spot.yuv 1920 1080 1.0 $P "OMC_H0_ZERO=1" "--gamut-strict 0" > spot10_zg0.txt 2>&1
bash $H gfx_g0 $P/still_gfx.yuv 448 256 0.5 $P "" "--gamut-strict 0" > gfx_g0.txt 2>&1
echo H0DONE > h0.done

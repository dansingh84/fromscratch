#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/tb
T=../notes/tb.sh; P=$PWD
bash $T gfx_10 $P/still_gfx.yuv 448 256 1.0 $P > gfx_10.txt 2>&1
bash $T dng720_05 $P/still_dng720.yuv 1280 720 0.5 $P > dng720_05.txt 2>&1
bash $T dng720_10 $P/still_dng720.yuv 1280 720 1.0 $P > dng720_10.txt 2>&1
bash $T spot_05 $P/still_spot.yuv 1920 1080 0.5 $P > spot_05.txt 2>&1
bash $T spot_10 $P/still_spot.yuv 1920 1080 1.0 $P > spot_10.txt 2>&1
bash $T real_dng720_05 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv 1280 720 0.5 $P dist > real_dng720_05.txt 2>&1
echo TBDONE > tb.done

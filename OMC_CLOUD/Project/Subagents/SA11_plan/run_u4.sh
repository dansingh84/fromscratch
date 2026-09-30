#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan
export OMC_R1_REUSE=1
U4=../SA7_legality_v2/rtree4/notes/u4.sh
AR=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
G=$AR/cf_gfx_448x256_422_10.yuv; SP=$AR/long/spotrobotL_1920x1080_422_10.yuv; DG=$AR/dng_1280x720_422_10.yuv
one() { # tag src W H bpp f s sh prof Q ns
  local t=$1 src=$2 W=$3 H=$4 R=$5 f=$6 s=$7 sh=$8 pr=$9 q=${10} ns=${11}
  bash $U4 $t $src $W $H 422 10 $R $f $s $sh u4
  for ((a=0; a<ns; a++)); do bash $U4 $t $src $W $H 422 10 $R $f $s $sh u4 $pr $q $a 0; done
}
one gfx_05 $G 448 256 0.5 0 15 8 0 10 13
one gfx_05 $G 448 256 0.5 0 26 8 0 10 22
one gfx8_05 $G 448 256 0.5 1 1 8 0 10 21
one gfx8_05 $G 448 256 0.5 4 4 8 0 10 13
one d7x8_05 $DG 1280 720 0.5 4 42 8 0 7 3
one spot_10 $SP 1920 1080 1.0 0 3 16 0 5 10
echo U4DONE

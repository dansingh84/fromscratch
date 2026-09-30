#!/bin/bash
# XS anchors: SVT JPEG XS (Agent3 build) at its best settings (A1_MEANS: --quantization 1 --rc 2 --slice-height 32), 12 frames
set -u
B=/home/user/fromscratch/OMC_CLOUD/Project/Agents/Agent3/tools/svtxs/Bin/Release
A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
T=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools
SCR=/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad
for c in "dng720 $A/dng_1280x720_422_10.yuv 1280 720" "spot $A/long/spotrobotL_1920x1080_422_10.yuv 1920 1080"; do
 set -- $c; N=$1; S=$2; W=$3; H=$4; FS=$((W*H*4))
 head -c $((FS*12)) $S > $SCR/${N}_12.yuv
 for R in 0.5 1.0 2.0; do
  LD_LIBRARY_PATH=$B $B/SvtJpegxsEncApp -i $SCR/${N}_12.yuv -b $SCR/x.jxs -w $W -h $H --colour-format yuv422 --input-depth 10 --bpp $R --quantization 1 --rc 2 --slice-height 32 --no-progress 1 -v 1 > /dev/null 2>&1 || { echo "ENC FAIL $N $R"; continue; }
  LD_LIBRARY_PATH=$B $B/SvtJpegxsDecApp -i $SCR/x.jxs -o $SCR/x.yuv -v 1 > /dev/null 2>&1 || { echo "DEC FAIL $N $R"; continue; }
  sz=$(stat -c%s $SCR/x.jxs)
  neg=$(bash $T/negscore.sh $SCR/${N}_12.yuv $SCR/x.yuv $W $H 422 10 12 2>/dev/null | tail -1)
  ps=$(python3 $T/planepsnr.py $SCR/${N}_12.yuv $SCR/x.yuv $W $H 422 10 12 xs 2>/dev/null | tail -1)
  echo "XS $N bpp_target=$R bytes=$sz bpp_actual=$(python3 -c "print(round($sz*8/($W*$H*12),3))") NEG=$neg | $ps"
  rm -f $SCR/x.yuv $SCR/x.jxs
 done
 for R in 0.5 1.0; do D=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/out/DM/${N}_b${R}_a0.d.yuv
  neg=$(bash $T/negscore.sh $SCR/${N}_12.yuv $D $W $H 422 10 12 2>/dev/null | tail -1)
  ps=$(python3 $T/planepsnr.py $SCR/${N}_12.yuv $D $W $H 422 10 12 today 2>/dev/null | tail -1)
  echo "TODAY-REAL(SA7 DM a0) $N bpp=$R NEG=$neg | $ps"
 done
done

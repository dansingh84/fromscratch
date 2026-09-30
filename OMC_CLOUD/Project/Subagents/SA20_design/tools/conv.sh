#!/bin/bash
# conv.sh CLIP W H FMT : PNG frames -> raw planar 10-bit (BT.709, limited range), Lanczos, full frame (no crop)
C=$1; W=$2; H=$3; F=$4; A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
PF=$([ "$F" = 444 ] && echo yuv444p10le || echo yuv422p10le)
ffmpeg -v error -y -framerate 25 -i ${C}_frame%03d.png -vf "scale=${W}:${H}:flags=lanczos+accurate_rnd+full_chroma_int:out_color_matrix=bt709:out_range=tv,format=$PF" -f rawvideo $A/${C}_${W}x${H}_${F}_10.yuv

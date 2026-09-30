#!/bin/bash
# negscore.sh REF.yuv DIST.yuv W H FMT DEPTH NFRAMES
#
# VMAF-NEG for an ARM-SHAPED file, with the pixel format chosen from the arm's
# own format and depth.  vmafneg.sh takes a raw ffmpeg pix_fmt and DEFAULTS to
# yuv422p10le, so every caller that omits it silently mis-scores 4:4:4 and
# non-10-bit arms.  Measured cost of getting it wrong on dng_1920x1080_422_12
# @0.5: 26.054 instead of 81.904 -- a 56-point error that looks like a result.
#
# The convention below is not invented here; it is the one that reproduces
# sect.40.6's published incumbent column EXACTLY on all four shapes:
#     422/10  yuv422p10le              -> 81.883
#     444/10  yuv444p10le              -> 81.501
#     422/12  yuv422p12le              -> 81.904
#     8-bit   both sides <<2, p10le    -> 81.893
# 8-bit arms are stored as <u2 containers holding 0..255, so they must be
# scaled into the 10-bit range before scoring or VMAF sees a near-black frame.
set -e
R=$1; D=$2; W=$3; H=$4; FMT=$5; DEP=$6; NF=$7
HD=$(dirname "$(readlink -f "$0")")
CH=$([ "$FMT" = 444 ] && echo yuv444p || echo yuv422p)
if [ "$DEP" = 8 ]; then
  RS=$(mktemp -u ${TMPDIR:-/tmp}/ns_r_XXXXXX).yuv
  DS=$(mktemp -u ${TMPDIR:-/tmp}/ns_d_XXXXXX).yuv
  python3 -c "
import numpy as np,sys
n=int(sys.argv[3])*int(sys.argv[4])*(3 if sys.argv[5]=='444' else 2)*int(sys.argv[6])
for s,d in ((sys.argv[1],sys.argv[7]),(sys.argv[2],sys.argv[8])):
    (np.fromfile(s,dtype='<u2',count=n)<<2).astype('<u2').tofile(d)
" "$R" "$D" "$W" "$H" "$FMT" "$NF" "$RS" "$DS"
  bash "$HD/vmafneg.sh" "$RS" "$DS" "$W" "$H" "$NF" "${CH}10le"
  rm -f "$RS" "$DS"
else
  bash "$HD/vmafneg.sh" "$R" "$D" "$W" "$H" "$NF" "${CH}${DEP}le"
fi

#!/bin/bash
# vmafneg.sh REF.yuv DIST.yuv W H NFRAMES [FMT]
# VMAF-NEG (vmaf_v0.6.1neg, luma-only by construction), 4 threads, EQUAL
# LENGTHS ONLY -- unequal lengths pool repeated-frame garbage (ledger F-31).
R=$1; D=$2; W=$3; H=$4; N=$5; FMT=${6:-yuv422p10le}
ffmpeg -v error -f rawvideo -pix_fmt $FMT -s ${W}x${H} -i "$D" \
       -f rawvideo -pix_fmt $FMT -s ${W}x${H} -i "$R" \
       -frames:v $N -lavfi "[0:v]trim=end_frame=$N[d];[1:v]trim=end_frame=$N[r];[d][r]libvmaf=model=path=/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json:n_threads=4:log_fmt=json:log_path=/dev/stdout" \
       -f null - 2>/dev/null | python3 -c "
import sys,json
j=json.load(sys.stdin); print('%.3f' % j['pooled_metrics']['vmaf']['mean'])"

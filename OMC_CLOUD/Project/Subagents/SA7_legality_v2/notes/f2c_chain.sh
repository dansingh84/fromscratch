#!/bin/bash
# [SA7/F2c] One 8-generation chain, F2c tree and the pristine control, same cell.
# Every exit code captured. Unique paths. Sequential: the control runs after F0.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
SRC=$ARMS/dng_1280x720_422_10.yuv; W=1280; H=720; NF=8; BPP=0.5
O=$A/out/F2CC; mkdir -p "$O"
chain() {  # tag treedir
  local tag=$1 T=$2 IN="$SRC" prev_pic="" prev_str="" g rc pic str moved ssame
  for g in 1 2 3 4 5 6 7 8; do
    nice -n 19 "$T/omc_enc" -i "$IN" -o "$O/${tag}_g$g.omc" -w $W -h $H --fmt 422 --depth 10 \
        --bpp $BPP -n $NF > "$O/${tag}_g$g.enc.log" 2>&1; rc=$?
    [ $rc -ne 0 ] && { echo "$tag g$g ENC rc=$rc"; return 1; }
    nice -n 19 "$T/omc_dec" -i "$O/${tag}_g$g.omc" -o "$O/${tag}_g$g.yuv" \
        > "$O/${tag}_g$g.dec.log" 2>&1; rc=$?
    [ $rc -ne 0 ] && { echo "$tag g$g DEC rc=$rc"; return 1; }
    pic=$(md5sum < "$O/${tag}_g$g.yuv" | cut -d' ' -f1)
    str=$(md5sum < "$O/${tag}_g$g.omc" | cut -d' ' -f1)
    moved="-"; [ -n "$prev_pic" ] && { [ "$pic" = "$prev_pic" ] && moved=0 || moved=NONZERO; }
    ssame="-"; [ -n "$prev_str" ] && { [ "$str" = "$prev_str" ] && ssame=SAME || ssame=DIFF; }
    echo "$tag g$g pic=$pic stream=$str moved_vs_prev=$moved stream_vs_prev=$ssame"
    prev_pic=$pic; prev_str=$str
    [ $g -gt 1 ] && rm -f "$O/${tag}_g$((g-1)).yuv"
    IN="$O/${tag}_g$g.yuv"
  done
  rm -f "$O/${tag}_g8.yuv"
  return 0
}
chain f2c  "$A/f2ctree"; echo "f2c chain rc=$?"
chain base "$A/basectl";  echo "base chain rc=$?"
echo "--- stream-by-stream F2c vs control ---"
for g in 1 2 3 4 5 6 7 8; do
  cmp -s "$O/f2c_g$g.omc" "$O/base_g$g.omc"; echo "g$g stream_cmp=$?"
done
echo CHAIN_DONE

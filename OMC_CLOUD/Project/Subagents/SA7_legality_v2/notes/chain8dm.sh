#!/bin/bash
# [SA7] 8-generation legal-baseband chain through the DISPLAY decode.
# usage: chain8.sh TAG SRC W H NF ARM   (ARM passed as OMC_SA7F to BOTH ends)
set -u
TAG=$1; SRC=$2; W=$3; H=$4; NF=$5; ARM=$6
E=${ENC:-ptree2/omc_enc}; D=${DEC:-ptree2/omc_dec}
IN="$SRC"
prev_pic=""; prev_str=""
for g in 1 2 3 4 5 6 7 8; do
  OMC_SA7F=$ARM nice -n 19 $E -i "$IN" -o out/DMC/${TAG}_g$g.omc -w $W -h $H --fmt 422 --depth 10 \
      --bpp 0.5 -n $NF 2> out/DMC/${TAG}_g$g.enc.log
  rc=$?; [ $rc -ne 0 ] && { echo "$TAG g$g ENC rc=$rc"; exit 1; }
  OMC_SA7F=$ARM nice -n 19 $D -i out/DMC/${TAG}_g$g.omc -o out/DMC/${TAG}_g$g.yuv 2>/dev/null
  rc=$?; [ $rc -ne 0 ] && { echo "$TAG g$g DEC rc=$rc"; exit 1; }
  pic=$(md5sum < out/DMC/${TAG}_g$g.yuv); str=$(md5sum < out/DMC/${TAG}_g$g.omc)
  moved="-"
  if [ -n "$prev_pic" ]; then
    if [ "$pic" = "$prev_pic" ]; then moved=0; else
      moved=$(cmp -l out/DMC/${TAG}_g$((g-1)).yuv out/DMC/${TAG}_g$g.yuv 2>/dev/null | wc -l); fi
  fi
  ssame="-"; [ -n "$prev_str" ] && { [ "$str" = "$prev_str" ] && ssame=SAME || ssame=DIFF; }
  echo "$TAG arm=$ARM g$g bytes_moved_vs_prev=$moved stream_vs_prev=$ssame oob=$(grep -oE 'gamut: -?[0-9]+' out/DMC/${TAG}_g$g.enc.log)"
  prev_pic=$pic; prev_str=$str
  [ $g -gt 1 ] && rm -f out/DMC/${TAG}_g$((g-1)).yuv
  IN=out/DMC/${TAG}_g$g.yuv
done
rm -f out/DMC/${TAG}_g8.yuv

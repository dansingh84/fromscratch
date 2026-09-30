#!/bin/bash
# [SA7-PO] DESIGN3 gate (1): the 8-generation legal-baseband chain through the
# DISPLAY decode, with the negative control (OMC_PO_CAP=0).
# The shipped repair AND the lattice correction engine are OFF in every arm, so
# the chain tests the transform and the encoder-only cap, nothing else.
# usage: po_chain.sh TAG SRC W H FMT DEPTH NF BPP CAP
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
TAG=$1; SRC=$2; W=$3; H=$4; FMT=$5; DEP=$6; NF=$7; BPP=$8; CAP=$9
E=$A/ptree6/omc_enc; D=$A/ptree6/omc_dec
O=$A/out/POC; mkdir -p "$O"
IN="$SRC"; prev_pic=""; prev_str=""
for g in 1 2 3 4 5 6 7 8; do
  b="$O/${TAG}_cap${CAP}_g$g"
  OMC_PO=1 OMC_PO_CAP=$CAP OMC_GM_LATT=0 nice -n 19 "$E" -i "$IN" -o "$b.omc" \
      -w $W -h $H --fmt $FMT --depth $DEP --bpp $BPP -n $NF --gamut-strict 0 \
      > "$b.enc.log" 2>&1; rc=$?
  [ $rc -ne 0 ] && { echo "$TAG cap=$CAP g$g ENC rc=$rc"; exit 1; }
  OMC_PO=1 nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dec.log" 2>&1; rc=$?
  [ $rc -ne 0 ] && { echo "$TAG cap=$CAP g$g DEC rc=$rc"; exit 1; }
  pic=$(md5sum < "$b.yuv" | cut -d' ' -f1); str=$(md5sum < "$b.omc" | cut -d' ' -f1)
  moved="-"; ssame="-"
  if [ -n "$prev_pic" ]; then
    if [ "$pic" = "$prev_pic" ]; then moved=0; else
      moved=$(cmp -l "$O/${TAG}_cap${CAP}_g$((g-1)).yuv" "$b.yuv" 2>/dev/null | wc -l); fi
  fi
  [ -n "$prev_str" ] && { [ "$str" = "$prev_str" ] && ssame=SAME || ssame=DIFF; }
  oob=$(grep -oE 'gamut: [0-9]+' "$b.enc.log" | grep -oE '[0-9]+')
  echo "$TAG cap=$CAP g$g bytes_moved_vs_prev=$moved stream_vs_prev=$ssame oob=${oob:-NA}"
  prev_pic=$pic; prev_str=$str
  [ $g -gt 1 ] && rm -f "$O/${TAG}_cap${CAP}_g$((g-1)).yuv"
  IN="$b.yuv"
done
rm -f "$O/${TAG}_cap${CAP}_g8.yuv"

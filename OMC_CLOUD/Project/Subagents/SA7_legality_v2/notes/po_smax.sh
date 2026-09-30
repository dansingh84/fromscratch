#!/bin/bash
# [SA7-PO] gate (2) follow-up: does the shift cap (the legality condition's
# allocation remedy) close the extrema, and is it free on real content?
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/ptree6/omc_enc; O=$A/out/PO2S; mkdir -p "$O"
run() {  # tag src w h fmt dep nf bpp smax
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8 sm=$9
  local b="$O/${t}_${fm}_${dp}_${bp}_s${sm}"
  OMC_PO=1 OMC_PO_CAP=1 OMC_PO_SMAX=$sm OMC_GM_LATT=0 OMC_PO_CAPSTAT=1 nice -n 19 "$E" \
     -i "$src" -o "$b.omc" -w $w -h $h --fmt $fm --depth $dp --bpp $bp -n $nf \
     --gamut-strict 0 > "$b.log" 2>&1
  local rc=$?
  local oob unreach bytes
  oob=$(grep -oE 'gamut: [0-9]+' "$b.log" | grep -oE '[0-9]+')
  unreach=$(grep '^PO_CAPSTAT TOTAL' "$b.log" | awk '{print $9}')
  bytes=$( [ -f "$b.omc" ] && stat -c %s "$b.omc" || echo NA )
  echo "SMAX t=$t $fm/$dp @$bp smax=$sm rc=$rc oob=${oob:-NA} unreached=${unreach:-NA} bytes=$bytes"
  rm -f "$b.omc"
}
for bp in 0.5 1.0 2.0; do for sm in 0 1; do
  run ext12 $A/arms/ext_12_422_l0.yuv 512 128 422 12 4 $bp $sm
  run ext10 $A/arms/ext_10_422_l0.yuv 512 128 422 10 4 $bp $sm
  run ext8  $A/arms/ext_8_422_l0.yuv  512 128 422  8 4 $bp $sm
done; done
for bp in 0.5 1.0 2.0; do for sm in 0 1; do
  run dng1080 $ARMS/dng_1920x1080_422_10.yuv 1920 1080 422 10 4 $bp $sm
  run gfx $ARMS/cf_gfx_448x256_422_10.yuv 448 256 422 10 4 $bp $sm
done; done
echo SMAX_DONE

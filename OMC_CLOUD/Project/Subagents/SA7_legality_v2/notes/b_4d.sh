#!/bin/bash
# [SA7-CP] arm (c), the 4d stack: oob after EACH stage, PC-all OFF.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/btree1/omc_enc; O=$A/out/B4D; mkdir -p "$O"
stage() {  # tag src w h fmt dep nf bpp stagename envextra
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8 sn=$9 ; shift 9
  local b="$O/${t}_${bp}_${sn}" rc
  env OMC_BCAP=1 OMC_BCAP_K=4 OMC_GM_LATT=0 OMC_BCAP_STAT=1 "$@" nice -n 19 "$E" \
     -i "$src" -o "$b.omc" -w $w -h $h --fmt $fm --depth $dp --bpp $bp -n $nf \
     --gamut-strict 0 > "$b.log" 2>&1; rc=$?
  local oob rows inf pct hr vc us esc
  oob=$(grep -oE 'gamut: [0-9]+' "$b.log" | grep -oE '[0-9]+')
  inf=$(grep '^BCAP ROWS' "$b.log" | sed 's/.*infeasible=\([0-9]*\).*/\1/')
  pct=$(grep '^BCAP ROWS' "$b.log" | sed 's/.*(\([0-9.]*\)%).*/\1/')
  hr=$(grep '^BCAP WORK' "$b.log" | sed 's/.*per_slice: h1rows=\([0-9.]*\).*/\1/')
  vc=$(grep '^BCAP WORK' "$b.log" | sed 's/.*v1cols=\([0-9.]*\).*/\1/')
  us=$(grep '^BCAP WORK' "$b.log" | sed 's/.*us_per_slice=\([0-9.]*\).*/\1/')
  esc=$(grep '^BESC TOTAL' "$b.log" | sed 's/.*escapes=\([0-9]*\).*/\1/')
  echo "B4D $t $fm/$dp @$bp stage=$sn rc=$rc oob=${oob:-NA} infeas_rows=${inf:-NA} pct=${pct:-NA} escapes=${esc:-0} bytes=$( [ -f $b.omc ] && stat -c %s $b.omc || echo NA) h1rows=${hr:-NA} v1cols=${vc:-NA} us=${us:-NA}"
  rm -f "$b.omc"
}
cell() {  # tag src w h fmt dep nf bpp maxK
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8 mk=$9
  stage $t $src $w $h $fm $dp $nf $bp cap
  stage $t $src $w $h $fm $dp $nf $bp esc OMC_BESC=1
  local k
  for k in $(seq 1 $mk); do
    stage $t $src $w $h $fm $dp $nf $bp cp$k OMC_BESC=1 OMC_BCP=1 OMC_BCP_K=$k
  done
}
cell dng720  $ARMS/dng_1280x720_422_10.yuv            1280  720 422 10 4 0.5 5
cell gfx     $ARMS/cf_gfx_448x256_422_10.yuv           448  256 422 10 4 0.5 5
cell spot    $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 4 0.5 2
cell spot    $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 4 1.0 2
cell dng444  $ARMS/dng_1920x1080_444_12.yuv           1920 1080 444 12 4 0.5 2
echo B4D_REAL_DONE

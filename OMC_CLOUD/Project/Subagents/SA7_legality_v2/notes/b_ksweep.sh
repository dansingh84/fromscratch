#!/bin/bash
# [SA7-B] rung 4c step (i): residue vs K greedy sweeps (2/4/8), with and without
# the two-candidate move at an even site.  Repair OFF, engine OFF.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/btree1/omc_enc; O=$A/out/BK; mkdir -p "$O"
pt() {  # tag src w h fmt dep nf bpp K 2C
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8 K=$9 C=${10}
  local b="$O/${t}_${fm}_${dp}_${bp}_K${K}_C${C}" rc
  OMC_BCAP=1 OMC_BCAP_K=$K OMC_BCAP_2C=$C OMC_GM_LATT=0 OMC_BCAP_STAT=1 \
    nice -n 19 "$E" -i "$src" -o "$b.omc" -w $w -h $h --fmt $fm --depth $dp \
    --bpp $bp -n $nf --gamut-strict 0 > "$b.log" 2>&1; rc=$?
  local oob rows inf pct sites hr vc us steps worst
  oob=$(grep -oE 'gamut: [0-9]+' "$b.log" | grep -oE '[0-9]+')
  rows=$(grep '^BCAP ROWS' "$b.log" | sed 's/.*total=\([0-9]*\).*/\1/')
  inf=$(grep '^BCAP ROWS' "$b.log" | sed 's/.*infeasible=\([0-9]*\).*/\1/')
  pct=$(grep '^BCAP ROWS' "$b.log" | sed 's/.*(\([0-9.]*\)%).*/\1/')
  sites=$(grep '^BCAP ROWS' "$b.log" | sed 's/.*sites_left=\([0-9]*\).*/\1/')
  hr=$(grep '^BCAP WORK' "$b.log" | sed 's/.*per_slice: h1rows=\([0-9.]*\).*/\1/')
  vc=$(grep '^BCAP WORK' "$b.log" | sed 's/.*v1cols=\([0-9.]*\).*/\1/')
  us=$(grep '^BCAP WORK' "$b.log" | sed 's/.*us_per_slice=\([0-9.]*\).*/\1/')
  steps=$(grep '^BCAP TOTAL' "$b.log" | awk '{print $5}')
  worst=$(grep -E '^BCAP (LH1|HL1|HH1|LH2|HL2|HH2|HL3|HL4|HL5|LL5)' "$b.log" | awk '{if($6>m)m=$6}END{print m+0}')
  echo "BK $t $fm/$dp @$bp K=$K 2C=$C rc=$rc oob=${oob:-NA} rows=${rows:-NA} infeas_rows=${inf:-NA} pct=${pct:-NA} sites=${sites:-NA} steps=${steps:-NA} worst=${worst:-NA} h1rows_per_slice=${hr:-NA} v1cols_per_slice=${vc:-NA} us_per_slice=${us:-NA}"
  rm -f "$b.omc"
}
for K in 2 4 8; do for C in 0 1; do
  for bp in 0.5 1.0 2.0; do
    pt dng720  $ARMS/dng_1280x720_422_10.yuv            1280  720 422 10 4 $bp $K $C
    pt dng1080 $ARMS/dng_1920x1080_422_10.yuv           1920 1080 422 10 4 $bp $K $C
    pt dng1080 $ARMS/dng_1920x1080_444_10.yuv           1920 1080 444 10 4 $bp $K $C
    pt spot    $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 4 $bp $K $C
    pt gfx     $ARMS/cf_gfx_448x256_422_10.yuv           448  256 422 10 4 $bp $K $C
    pt ext10   $A/arms/ext_10_422_l0.yuv                 512  128 422 10 4 $bp $K $C
  done
  pt cut24 $A/arms/cut24.yuv 256 64 422 10 24 1.0 $K $C
done; done
echo BK_DONE

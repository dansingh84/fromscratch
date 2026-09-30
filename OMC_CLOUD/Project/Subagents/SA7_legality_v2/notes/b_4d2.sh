#!/bin/bash
# [SA7-CP] 4d, rail content: cut24 and the extrema, constructive pass at ONE pass.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
E=$A/btree1/omc_enc; O=$A/out/B4D2; mkdir -p "$O"
st() { local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8 sn=$9; shift 9
  local b="$O/${t}_${bp}_${sn}" rc
  env OMC_BCAP=1 OMC_BCAP_K=4 OMC_GM_LATT=0 OMC_BCAP_STAT=1 "$@" nice -n 19 "$E" \
     -i "$src" -o "$b.omc" -w $w -h $h --fmt $fm --depth $dp --bpp $bp -n $nf \
     --gamut-strict 0 > "$b.log" 2>&1; rc=$?
  echo "B4D2 $t $fm/$dp @$bp stage=$sn rc=$rc oob=$(grep -oE 'gamut: [0-9]+' $b.log|grep -oE '[0-9]+'|head -1) pct=$(grep '^BCAP ROWS' $b.log | sed 's/.*(\([0-9.]*\)%).*/\1/') us=$(grep '^BCAP WORK' $b.log | sed 's/.*us_per_slice=\([0-9.]*\).*/\1/')"
  rm -f "$b.omc"; }
for t in "cut24 $A/arms/cut24.yuv 256 64 422 10 24 0.5" \
         "cut24 $A/arms/cut24.yuv 256 64 422 10 24 1.0" \
         "extFULL $A/arms/ext_10_422_l0.yuv 512 128 422 10 4 1.0" \
         "extLIM $A/arms/ext_10_422_l1.yuv 512 128 422 10 4 1.0"; do
  set -- $t
  st $1 $2 $3 $4 $5 $6 $7 $8 cap
  st $1 $2 $3 $4 $5 $6 $7 $8 esc OMC_BESC=1
  st $1 $2 $3 $4 $5 $6 $7 $8 cp1 OMC_BESC=1 OMC_BCP=1 OMC_BCP_K=1
done
echo B4D2_DONE

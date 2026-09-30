#!/bin/bash
# [SA7-POC] (A) the split curve: predict-only at the coarse horizontal levels.
# Engine and repair OFF in every arm so only the transform differs.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
O=$A/out/POC; mkdir -p "$O"
pt() {  # tag src w h fmt dep nf bpp armname enc envspec
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8 an=$9 E=${10}; shift 10
  local b="$O/${t}_${bp}_${an}" rc1 rc2
  env "$@" OMC_GM_LATT=0 OMC_EXC_STAT=1 nice -n 19 "$E" -i "$src" -o "$b.omc" \
      -w $w -h $h --fmt $fm --depth $dp --bpp $bp -n $nf --gamut-strict 0 \
      > "$b.log" 2>&1; rc1=$?
  local dec=${E%/*}/omc_dec
  env "$@" nice -n 19 "$dec" -i "$b.omc" -o "$b.yuv" > "$b.dl" 2>&1; rc2=$?
  local oob p50 p99 mx
  oob=$(grep -oE 'gamut: [0-9]+' "$b.log" | grep -oE '[0-9]+' | head -1)
  read p50 p99 mx <<< "$(grep '^EXC ' "$b.log" | awk '{print $2}' | sort -n | awk '{v[n++]=$1} END{if(n==0){print "0 0 0"}else{printf "%d %d %d\n", v[int(n*0.5)], v[int(n*0.99)], v[n-1]}}')"
  echo "POC $t $fm/$dp @$bp arm=$an rc=$rc1/$rc2 oob=${oob:-NA} exc_p50=$p50 exc_p99=$p99 exc_max=$mx bytes=$( [ -f $b.omc ] && stat -c %s $b.omc || echo NA)"
  [ $rc2 -eq 0 ] && python3 "$A/notes/po_psnr.py" "$src" "$b.yuv" $w $h $fm $dp $nf "$t @$bp $an"
  rm -f "$b.yuv" "$b.omc"; }
for c in "dng720 $ARMS/dng_1280x720_422_10.yuv 1280 720 422 10 4 0.5" \
         "spot $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 4 0.5" \
         "gfx $ARMS/cf_gfx_448x256_422_10.yuv 448 256 422 10 4 0.5" \
         "cut24 $A/arms/cut24.yuv 256 64 422 10 24 1.0"; do
  set -- $c
  pt $1 $2 $3 $4 $5 $6 $7 $8 base   $A/btree1/omc_enc OMC_POC=0
  pt $1 $2 $3 $4 $5 $6 $7 $8 L5     $A/btree1/omc_enc OMC_POC=32
  pt $1 $2 $3 $4 $5 $6 $7 $8 L45    $A/btree1/omc_enc OMC_POC=48
  pt $1 $2 $3 $4 $5 $6 $7 $8 L345   $A/btree1/omc_enc OMC_POC=56
  pt $1 $2 $3 $4 $5 $6 $7 $8 ALL    $A/ptree6/omc_enc OMC_PO=1
done
echo POC_DONE

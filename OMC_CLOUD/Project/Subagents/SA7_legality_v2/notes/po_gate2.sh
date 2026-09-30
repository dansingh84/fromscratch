#!/bin/bash
# [SA7-PO] DESIGN3 gate (2): oob = 0 across every depth, format, range and rate,
# with the shipped repair AND the lattice correction engine OFF, plus the
# cap-binding counter (steps moved per band) and the cap-off negative control.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/ptree6/omc_enc; D=$A/ptree6/omc_dec
O=$A/out/PO2; mkdir -p "$O"
point() {   # tag src w h fmt depth nf bpp
  local tag=$1 src=$2 w=$3 h=$4 fmt=$5 dep=$6 nf=$7 bpp=$8
  local b="$O/${tag}_${fmt}_${dep}_${bpp}"
  local r1 r2 r3 on off dec
  OMC_PO=1 OMC_PO_CAP=1 OMC_GM_LATT=0 OMC_PO_CAPSTAT=1 nice -n 19 "$E" \
      -i "$src" -o "$b.on.omc" -w $w -h $h --fmt $fmt --depth $dep --bpp $bpp \
      -n $nf --gamut-strict 0 > "$b.on.log" 2>&1; r1=$?
  OMC_PO=1 OMC_PO_CAP=0 OMC_GM_LATT=0 nice -n 19 "$E" \
      -i "$src" -o "$b.off.omc" -w $w -h $h --fmt $fmt --depth $dep --bpp $bpp \
      -n $nf --gamut-strict 0 > "$b.off.log" 2>&1; r2=$?
  OMC_PO=1 nice -n 19 "$D" -i "$b.on.omc" -o "$b.yuv" > "$b.dec.log" 2>&1; r3=$?
  on=$(grep -oE 'gamut: [0-9]+' "$b.on.log"  | grep -oE '[0-9]+')
  off=$(grep -oE 'gamut: [0-9]+' "$b.off.log" | grep -oE '[0-9]+')
  local bind steps worst
  bind=$(grep '^PO_CAPSTAT TOTAL' "$b.on.log" | awk '{print $4}')
  steps=$(grep '^PO_CAPSTAT TOTAL' "$b.on.log" | awk '{print $6}')
  worst=$(grep '^PO_CAPSTAT HH' "$b.on.log" | awk '{if($8>m)m=$8}END{print m+0}')
  echo "P2 $tag $fmt/$dep @$bpp rc=$r1/$r2/$r3 oob_cap_on=${on:-NA} oob_cap_off=${off:-NA} bind%=${bind:-NA} steps=${steps:-NA} hh_worst_steps=${worst:-NA}"
  grep '^PO_CAPSTAT' "$b.on.log" | sed "s|^|CAPSTAT $tag $fmt/$dep @$bpp |" >> "$O/capstat.txt"
  rm -f "$b.yuv" "$b.on.omc" "$b.off.omc"
}
: > "$O/capstat.txt"
for bpp in 0.5 1.0 2.0; do
  # ---- A. real content, full range, every depth and format
  for dep in 8 10 12; do
    point dng1080 $ARMS/dng_1920x1080_422_$dep.yuv 1920 1080 422 $dep 4 $bpp
    point dng1080 $ARMS/dng_1920x1080_444_$dep.yuv 1920 1080 444 $dep 4 $bpp
  done
  # ---- B. real content, LIMITED range
  point dngLIM $A/arms/dngL_1920x1080_422_10.yuv 1920 1080 422 10 4 $bpp
  # ---- C. synthetic extrema, full and limited range, every depth and format
  for dep in 8 10 12; do for fm in 422 444; do for l in 0 1; do
    point ext$( [ $l = 1 ] && echo LIM || echo FULL ) \
          $A/arms/ext_${dep}_${fm}_l${l}.yuv 512 128 $fm $dep 4 $bpp
  done; done; done
  # ---- D. the G-T5-CUT24 rail-plate cut sequence
  point cut24 "$A/arms/cut24.yuv" 256 64 422 10 24 $bpp
  # ---- E. dense-rail graphics
  point gfx $ARMS/cf_gfx_448x256_422_10.yuv 448 256 422 10 4 $bpp
done
echo GATE2_DONE

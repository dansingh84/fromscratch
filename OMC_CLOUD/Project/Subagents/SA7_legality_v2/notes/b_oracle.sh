#!/bin/bash
# [SA7-B] L-I28 oracle, measurement (1)(2)(5): the infeasibility table.
# Repair OFF and the lattice correction engine OFF in every arm; the cap-off
# control runs beside each point; every exit code captured.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/btree1/omc_enc; O=$A/out/B1; mkdir -p "$O"
: > "$O/bands.txt"
point() {  # tag src w h fmt dep nf bpp
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8
  local b="$O/${t}_${fm}_${dp}_${bp}" r1 r2 on off
  OMC_BCAP=1 OMC_BCAP_CAP=1 OMC_GM_LATT=0 OMC_BCAP_STAT=1 nice -n 19 "$E" \
     -i "$src" -o "$b.on.omc" -w $w -h $h --fmt $fm --depth $dp --bpp $bp -n $nf \
     --gamut-strict 0 > "$b.on.log" 2>&1; r1=$?
  OMC_BCAP=1 OMC_BCAP_CAP=0 OMC_GM_LATT=0 nice -n 19 "$E" \
     -i "$src" -o "$b.off.omc" -w $w -h $h --fmt $fm --depth $dp --bpp $bp -n $nf \
     --gamut-strict 0 > "$b.off.log" 2>&1; r2=$?
  on=$(grep -oE 'gamut: [0-9]+' "$b.on.log"  | grep -oE '[0-9]+')
  off=$(grep -oE 'gamut: [0-9]+' "$b.off.log" | grep -oE '[0-9]+')
  local rows inf pct sites viol tot narrow steps worst
  rows=$(grep '^BCAP ROWS' "$b.on.log" | sed 's/.*total=\([0-9]*\).*/\1/')
  inf=$(grep '^BCAP ROWS' "$b.on.log" | sed 's/.*infeasible=\([0-9]*\).*/\1/')
  pct=$(grep '^BCAP ROWS' "$b.on.log" | sed 's/.*(\([0-9.]*\)%).*/\1/')
  sites=$(grep '^BCAP ROWS' "$b.on.log" | sed 's/.*sites_left=\([0-9]*\).*/\1/')
  viol=$(grep '^BCAP ROWS' "$b.on.log" | sed 's/.*violations_seen=\([0-9]*\).*/\1/')
  tot=$(grep '^BCAP TOTAL' "$b.on.log" | awk '{print $6}')
  narrow=$(grep '^BCAP TOTAL' "$b.on.log" | awk '{print $7}')
  steps=$(grep '^BCAP TOTAL' "$b.on.log" | awk '{print $5}')
  worst=$(grep -E '^BCAP (LL5|HL5|HL4|HL3|LH2|HL2|HH2|LH1|HL1|HH1)' "$b.on.log" | awk '{if($6>m)m=$6}END{print m+0}')
  echo "B1 $t $fm/$dp @$bp rc=$r1/$r2 oob_on=${on:-NA} oob_off=${off:-NA} rows=${rows:-NA} infeas_rows=${inf:-NA} infeas_row_pct=${pct:-NA} sites_left=${sites:-NA} viol_seen=${viol:-NA} infeas_sites=${tot:-NA} step_gt_window=${narrow:-NA} steps=${steps:-NA} worst_steps=${worst:-NA}"
  grep '^BCAP ' "$b.on.log" | sed "s|^|BANDS $t $fm/$dp @$bp |" >> "$O/bands.txt"
  rm -f "$b.on.omc" "$b.off.omc"
}
for bp in 0.5 1.0 2.0; do
  point dng720  $ARMS/dng_1280x720_422_10.yuv            1280  720 422 10 4 $bp
  for dp in 8 10 12; do
    point dng1080 $ARMS/dng_1920x1080_422_$dp.yuv        1920 1080 422 $dp 4 $bp
    point dng1080 $ARMS/dng_1920x1080_444_$dp.yuv        1920 1080 444 $dp 4 $bp
  done
  point dngLIM  $A/arms/dngL_1920x1080_422_10.yuv        1920 1080 422 10 4 $bp
  point spot    $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 4 $bp
  point gfx     $ARMS/cf_gfx_448x256_422_10.yuv           448  256 422 10 4 $bp
  point cut24   $A/arms/cut24.yuv                         256   64 422 10 24 $bp
  for dp in 8 10 12; do for fm in 422 444; do for l in 0 1; do
    point ext$( [ $l = 1 ] && echo LIM || echo FULL ) $A/arms/ext_${dp}_${fm}_l${l}.yuv \
          512 128 $fm $dp 4 $bp
  done; done; done
done
echo B1_DONE

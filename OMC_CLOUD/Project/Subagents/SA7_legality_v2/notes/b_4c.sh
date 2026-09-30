#!/bin/bash
# [SA7-B] rung 4c step (ii): the cap at K=4 plus bank-funded escapes.
# Repair OFF, engine OFF, cap-off control beside every point.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/btree1/omc_enc; D=$A/btree1/omc_dec; O=$A/out/B4; mkdir -p "$O"
pt() {  # tag src w h fmt dep nf bpp
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8
  local b="$O/${t}_${fm}_${dp}_${bp}" r1 r2 r3
  OMC_BCAP=1 OMC_BCAP_K=4 OMC_BESC=1 OMC_GM_LATT=0 OMC_BCAP_STAT=1 OMC_BESC_STAT=1 \
    nice -n 19 "$E" -i "$src" -o "$b.on.omc" -w $w -h $h --fmt $fm --depth $dp \
    --bpp $bp -n $nf --gamut-strict 0 > "$b.on.log" 2>&1; r1=$?
  OMC_GM_LATT=0 nice -n 19 "$E" -i "$src" -o "$b.off.omc" -w $w -h $h --fmt $fm \
    --depth $dp --bpp $bp -n $nf --gamut-strict 0 > "$b.off.log" 2>&1; r2=$?
  nice -n 19 "$D" -i "$b.on.omc" -o "$b.yuv" > "$b.dec.log" 2>&1; r3=$?
  local on off rows inf pct esc ew eb ov sb
  on=$(grep -oE 'gamut: [0-9]+' "$b.on.log"  | grep -oE '[0-9]+')
  off=$(grep -oE 'gamut: [0-9]+' "$b.off.log" | grep -oE '[0-9]+')
  rows=$(grep '^BCAP ROWS' "$b.on.log" | sed 's/.*total=\([0-9]*\).*/\1/')
  inf=$(grep '^BCAP ROWS' "$b.on.log" | sed 's/.*infeasible=\([0-9]*\).*/\1/')
  pct=$(grep '^BCAP ROWS' "$b.on.log" | sed 's/.*(\([0-9.]*\)%).*/\1/')
  esc=$(grep '^BESC TOTAL' "$b.on.log" | sed 's/.*escapes=\([0-9]*\).*/\1/')
  ew=$(grep '^BESC TOTAL' "$b.on.log" | sed 's/.*worst_per_slice=\([0-9]*\).*/\1/')
  eb=$(grep '^BESC TOTAL' "$b.on.log" | sed 's/.*worst_bits=\([0-9]*\).*/\1/')
  ov=$(grep '^BESC TOTAL' "$b.on.log" | sed 's/.*overflow=\([0-9]*\).*/\1/')
  sb=$(grep '^BESC slice' "$b.on.log" | head -1 | sed 's/.*slice_bytes=\([0-9]*\).*/\1/')
  local pctsl=NA pctcap=NA
  if [ -n "${eb:-}" ] && [ -n "${sb:-}" ] && [ "${sb:-0}" != 0 ]; then
    pctsl=$(python3 -c "print('%.3f'%(100.0*$eb/8.0/$sb))")
    pctcap=$(python3 -c "print('%.3f'%(100.0*$eb/8.0/(2.0*$sb)))")
  fi
  echo "B4 $t $fm/$dp @$bp rc=$r1/$r2/$r3 oob_armed=${on:-NA} oob_control=${off:-NA} rows=${rows:-NA} infeas_rows=${inf:-NA} pct=${pct:-NA} escapes=${esc:-0} esc_worst_slice=${ew:-0} esc_worst_bits=${eb:-0} overflow=${ov:-0} slice_bytes=${sb:-NA} pct_of_slice=$pctsl pct_of_wirecap=$pctcap"
  rm -f "$b.yuv" "$b.on.omc" "$b.off.omc"
}
for bp in 0.5 1.0 2.0; do
  pt dng720  $ARMS/dng_1280x720_422_10.yuv            1280  720 422 10 4 $bp
  for dp in 8 10 12; do
    pt dng1080 $ARMS/dng_1920x1080_422_$dp.yuv        1920 1080 422 $dp 4 $bp
    pt dng1080 $ARMS/dng_1920x1080_444_$dp.yuv        1920 1080 444 $dp 4 $bp
  done
  pt dngLIM  $A/arms/dngL_1920x1080_422_10.yuv        1920 1080 422 10 4 $bp
  pt spot    $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 4 $bp
  pt gfx     $ARMS/cf_gfx_448x256_422_10.yuv           448  256 422 10 4 $bp
  pt extFULL $A/arms/ext_10_422_l0.yuv                  512  128 422 10 4 $bp
  pt extLIM  $A/arms/ext_10_422_l1.yuv                  512  128 422 10 4 $bp
done
pt cut24 $A/arms/cut24.yuv 256 64 422 10 24 1.0
echo B4_DONE

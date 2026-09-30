#!/bin/bash
# [SA7-2x2] {cap off,on} x {escapes off,on}, SHIPPED ENGINE ON in every arm.
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
E=$A/btree1/omc_enc; D=$A/btree1/omc_dec; O=$A/out/B2X; mkdir -p "$O"
run() {  # tag src w h nf bpp arm K
  local t=$1 src=$2 w=$3 h=$4 nf=$5 bp=$6 arm=$7 KF=$8
  local b="$O/${t}_${bp}_${arm}" r1 r2 EV=""
  case $arm in
    base)    EV="" ;;
    cap)     EV="OMC_BCAP=1 OMC_BCAP_K=4" ;;
    esc)     EV="OMC_BCAP=1 OMC_BCAP_CAP=0 OMC_BESC=1" ;;
    capesc)  EV="OMC_BCAP=1 OMC_BCAP_K=4 OMC_BESC=1" ;;
  esac
  env $EV OMC_GM_PERSLICE=1 nice -n 19 "$E" -i "$src" -o "$b.omc" -w $w -h $h \
      --fmt 422 --depth 10 --bpp $bp -n $nf > "$b.log" 2>&1; r1=$?
  nice -n 19 "$D" -i "$b.omc" -o "$b.yuv" > "$b.dl" 2>&1; r2=$?
  local oob safe tp
  oob=$(grep -oE 'gamut: [0-9]+' "$b.log" | grep -oE '[0-9]+' | head -1)
  safe=$(grep -oE 'baseband-safe: [a-zA-Z]+' "$b.log" | awk '{print $2}')
  tp=$(grep -oE 'repaired in [0-9]+ passes' "$b.log" | grep -oE '[0-9]+' | head -1)
  local stats
  stats=$(grep '^GMSLICE' "$b.log" | awk -v K=$KF '
    {key=$2"_"$3; m[key]=$4}
    END{n=0; for(k in m){v[n++]=m[k]; if(m[k]>K)over++}
        for(i=0;i<n;i++)for(j=i+1;j<n;j++)if(v[i]>v[j]){t=v[i];v[i]=v[j];v[j]=t}
        if(n==0){print "0 0 0 0 0"} else
        printf "%d %d %d %d %d\n", v[int(n*0.5)], v[int(n*0.9)], v[n-1], over+0, n}')
  echo "B2X $t @$bp arm=$arm rc=$r1/$r2 oob=${oob:-NA} safe=${safe:-NA} total_passes=${tp:-0} p50/p90/max/overK/slices=$stats bytes=$( [ -f $b.omc ] && stat -c %s $b.omc || echo NA)"
  [ $r2 -eq 0 ] && python3 "$A/notes/po_psnr.py" "$src" "$b.yuv" $w $h 422 10 $nf "$t @$bp $arm"
  rm -f "$b.yuv" "$b.omc"; }
for arm in base cap esc capesc; do
  run dng720 $ARMS/dng_1280x720_422_10.yuv 1280 720 8 0.5 $arm 5
done
for arm in base cap esc capesc; do
  run spot $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 8 0.5 $arm 2
done
echo B2X_DONE

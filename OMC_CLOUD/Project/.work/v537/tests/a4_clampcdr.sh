#!/bin/bash
# sect.B3.7f: CLAMP ships CDR-scoped.  12-generation CDR chains, clamp mode
# (--no-gamut-strict) at EVERY generation, across the implemented gamut.
cd /home/user/fromscratch/OMC_CLOUD/Project/.work
E=v54tree/omc_enc; D=v54tree/omc_dec
export TMPDIR=$PWD/scratch/tmp
a4(){ A=$1; WD=$2; HT=$3; FMT=$4; DP=$5; BPP=$6; NF=$7; G=$8
  free=$(df --output=avail -B1M $PWD | tail -1)
  need=$(( WD*HT*4*NF*(G+1)/1000000 + 512 ))
  [ "$free" -lt "$need" ] && { echo "HARNESS ERROR: disk $free MB < $need MB"; return 99; }
  tmp=$(mktemp -d $PWD/scratch/tmp/a4.XXXXXX)
  cur=$A; SH=$([ $HT -le 720 ] && echo 8 || echo 16); CHh=$(( (HT+SH-1)/SH*SH ))
  ok=PASS; why=""
  for g in $(seq 1 $G); do
    if [ $g -gt 1 ]; then
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $CHh --fmt $FMT --depth $DP --bpp $BPP -n $NF --display-w $WD --display-h $HT --cdr-in --no-gamut-strict >/dev/null 2>&1
    else
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n $NF --no-gamut-strict >/dev/null 2>&1
    fi
    [ -s $tmp/s$g.omc ] || { ok=FAIL; why="enc-gen$g"; break; }
    $D -i $tmp/s$g.omc --cdr -o $tmp/d$g.yuv >/dev/null 2>&1
    [ -s $tmp/d$g.yuv ] || { ok=FAIL; why="dec-gen$g"; break; }
    if [ $g -ge 2 ]; then
      cmp -s $tmp/d$g.yuv $tmp/d$((g-1)).yuv || { ok=FAIL; why="pixels-gen$g"; break; }
      [ $g -ge 3 ] && { cmp -s $tmp/s$g.omc $tmp/s$((g-1)).omc || { ok=FAIL; why="stream-gen$g"; break; }; }
    fi
    cur=$tmp/d$g.yuv
  done
  echo "A4-CDR-CLAMP $(basename $A .yuv)@$BPP/$FMT-$DP gens=$G : $ok $why"
  rm -rf $tmp
}
a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 1.0 12 12
a4 arms/cityalley_1920x1080_422_10.yuv 1920 1080 422 10 1.0 12 12
a4 arms/bosphorus_1920x1080_422_10.yuv 1920 1080 422 10 2.0 12 12
a4 arms/dng_1920x1080_422_10.yuv 1920 1080 422 10 0.5 12 12
a4 arms/dng_1280x720_422_10.yuv 1280 720 422 10 1.0 12 12
a4 arms/dng_1920x1080_444_10.yuv 1920 1080 444 10 1.0 12 12
a4 arms/dng_1920x1080_444_10.yuv 1920 1080 444 10 0.5 12 12
a4 arms/dng_1920x1080_444_12.yuv 1920 1080 444 12 0.5 12 12
a4 arms/dng_1920x1080_422_8.yuv 1920 1080 422 8 2.0 12 12
a4 arms/dng_1920x1080_444_12.yuv 1920 1080 444 12 1.0 12 12
a4 arms/cf_gfx_448x256_422_10.yuv 448 256 422 10 0.5 12 12
a4 arms/readysetgo_1920x1080_422_10.yuv 1920 1080 422 10 4.0 12 12
echo CDR-CLAMP-DONE

#!/bin/bash
# [SA7-R1] discriminator (a): does the lattice read return generation 1's plan?
set -u
A=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2
S=/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad
E=$A/rtree1/omc_enc; D=$A/rtree1/omc_dec
one() {  # tag src w h fmt dep nf bpp fix1 fix2 extra
  local t=$1 src=$2 w=$3 h=$4 fm=$5 dp=$6 nf=$7 bp=$8 f1=$9 f2=${10}; shift 10
  local O=$S/rr_$$; rm -rf $O; mkdir -p $O; local IN=$src g
  for g in 1 2; do
    OMC_R1=1 OMC_GM_LATT=0 OMC_R1_PLANREAD=1 OMC_R1_FIX1=$f1 OMC_R1_FIX2=$f2 \
      nice -n 19 "$E" -i "$IN" -o $O/g$g.omc -w $w -h $h --fmt $fm --depth $dp \
      --bpp $bp -n $nf --gamut-strict 0 "$@" 2>$O/g$g.plan >/dev/null || { echo "$t ENC fail"; return; }
    OMC_R1=1 nice -n 19 "$D" -i $O/g$g.omc -o $O/g$g.yuv >/dev/null 2>&1
    IN=$O/g$g.yuv
  done
  python3 - "$O" "$t @$bp fix1=$f1 fix2=$f2 $*" <<'PY'
import re,sys
O,tag=sys.argv[1],sys.argv[2]
def load(f):
    out={}
    for ln in open(f):
        m=re.match(r'R1PLAN f=(\d+) s=(\d+) agree=\d+ of=\d+ fallback=(\d+)\s+(.*)',ln)
        if m: out[(m.group(1),m.group(2))]=([tuple(map(int,t.split('/'))) for t in m.group(4).split() if '/' in t], int(m.group(3)))
    return out
g1=load(O+'/g1.plan'); g2=load(O+'/g2.plan')
ok=tot=sl=slok=fb=0
for k in g1:
    if k not in g2: continue
    sl+=1; good=True; fb+=g2[k][1]
    for (r1,w1),(r2,w2) in zip(g1[k][0],g2[k][0]):
        if r2<0: continue
        tot+=1
        if r2==w1: ok+=1
        else: good=False
    if good: slok+=1
print('R1READ %-42s bands %5d/%5d (%5.1f%%)  slices %3d/%3d (%5.1f%%)  fallback %d'
      %(tag,ok,tot,100.0*ok/max(1,tot),slok,sl,100.0*slok/max(1,sl),fb))
PY
  rm -rf $O; }
ARMS=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
for cell in "dng720 $ARMS/dng_1280x720_422_10.yuv 1280 720 422 10 4 0.5" \
            "spot $ARMS/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 422 10 4 0.5" \
            "gfx $ARMS/cf_gfx_448x256_422_10.yuv 448 256 422 10 4 0.5"; do
  set -- $cell
  one $1 $2 $3 $4 $5 $6 $7 $8 0 0
  one $1 $2 $3 $4 $5 $6 $7 $8 1 0
  one $1 $2 $3 $4 $5 $6 $7 $8 1 1
  one $1 $2 $3 $4 $5 $6 $7 $8 1 1 --refresh 1
done
echo R1READ_DONE

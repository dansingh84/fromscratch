#!/bin/bash
# item 1: error continuation on INTRA frames (frame 0 = all intra): CONT 0/8/16, per cell and slice height
export SCR=/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad
N=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA12_design/notes; A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms; T=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools
run(){ tag=$1; src=$2; W=$3; H=$4; sh=$5; f0=$6; c=$7
  SEQ_OBMC=1 SEQ_BELOW=1 SEQ_CONT=$c SEQ_CW=$CWV nice -n 19 python3 $N/seq.py $src $W $H $f0 1 $sh 6.0 ${tag}_c${c}w$CWV > ${tag}_c${c}w$CWV.log 2>&1 || { echo "FAIL $tag $c"; return; }
  ex=$(python3 $N/intrastep.py $SCR/${tag}_c${c}w$CWV.src.yuv $SCR/${tag}_c${c}w$CWV.dec.yuv $W $H $sh 0)
  neg=$(bash $T/negscore.sh $SCR/${tag}_c${c}w$CWV.src.yuv $SCR/${tag}_c${c}w$CWV.dec.yuv $W $H 422 10 1 2>/dev/null | tail -1)
  ps=$(python3 -c "import json;d=json.load(open('${tag}_c${c}w$CWV.seq.json'));print('bpp(ent) %.3f PSNR %s'%(d['bpp'][0],'/'.join('%.2f'%x for x in d['psnr'][0])))")
  echo "$tag sh$sh CONT=$c | NEG $neg | $ps | intra boundary excess $ex"; rm -f $SCR/${tag}_c${c}w$CWV.*.yuv
}
for cw in "4 0.5" "8 0.5" "4 1"; do set -- $cw; c=$1; CWV=$2
 run spot16 $A/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 16 8 $c &
 run d720 $A/dng_1280x720_422_10.yuv 1280 720 8 8 $c &
 wait
done

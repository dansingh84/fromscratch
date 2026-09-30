cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out
until grep -q DONE eval_c.log; do sleep 30; done
T=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools
A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
declare -A SRC=( [dng720]="$A/dng_1280x720_422_10.yuv 1280 720 4" [dng1080]="$A/dng_1920x1080_422_10.yuv 1920 1080 8" [spot]="$A/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 8" [floor]="$A/long/floorballgameL_1920x1080_422_10.yuv 1920 1080 8" [hwy]="$A/long/highwaydriveL_1920x1080_422_10.yuv 1920 1080 8" [volley]="$A/long/volleyballgameL_1920x1080_422_10.yuv 1920 1080 8" )
declare -A TOD=( [dng720]=../../SA7_legality_v2/out/DM/dng720_b%s_a0.d.yuv [dng1080]=../../SA7_legality_v2/out/DM/dng1080_b%s_a0.d.yuv [spot]=../../SA7_legality_v2/out/DM/spot_b%s_a0.d.yuv [floor]=../../SA15_design/out/today/floor_b%s.d.yuv [hwy]=../../SA15_design/out/today/hwy_b%s.d.yuv [volley]=../../SA15_design/out/today/volley_b%s.d.yuv )
for c in dng720 dng1080 spot floor hwy volley; do for b in 0.5 1.0; do
  set -- ${SRC[$c]}; S=$1; W=$2; H=$3; SH=$4
  for arm in mine today; do
    if [ $arm = mine ]; then D=dec/c1_${c}_b$b.d.yuv; else D=$(printf ${TOD[$c]} $b); fi
    L=art/${arm}_${c}_$b; mkdir -p $L
    { echo "== $arm $c @$b"
      python3 $T/smudgegroups.py $S $D $W $H 6 $L/sg --sh $SH 2>&1 | tail -3
      for pl in Y Cb Cr; do python3 $T/artifactmap.py $S $D $W $H 6 $L --plane $pl --slice-h $SH 2>&1 | tail -1; done
      python3 $T/flatplane.py $S $D $W $H 6 2>&1 | tail -4
      python3 $T/rowphase.py $S $D $W $H 12 --sh $SH --label ${arm}_${c}_$b 2>&1 | grep spread
    } >> art/summary.log 2>&1
  done
done; done
echo ARTDONE >> art/summary.log

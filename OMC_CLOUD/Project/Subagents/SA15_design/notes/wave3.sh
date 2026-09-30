run(){ tag=$1; shift; a1=$1;a2=$2;a3=$3;a4=$4;a5=$5; shift 5; ( TABLES=${TB:-../out/tables_B.pkl} timeout 40000 nice -n 19 python3 run2.py $a1 $a2 $a3 $a4 $a5 $tag "$@" > ../out/r2/log/$tag.txt 2>&1; echo rc=$? >> ../out/r2/log/$tag.txt ) & }
TB=../out/tables_A.pkl run floor_0.5_tabA /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/floorballgameL_1920x1080_422_10.yuv 1920 1080 0.5 12 --gen2 0
TB=../out/tables_A.pkl run hwy_0.5_tabA /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/highwaydriveL_1920x1080_422_10.yuv 1920 1080 0.5 12 --gen2 0
run floor_0.5_hp /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/floorballgameL_1920x1080_422_10.yuv 1920 1080 0.5 12 --hp 1 --gen2 0
run hwy_0.5_hp /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/highwaydriveL_1920x1080_422_10.yuv 1920 1080 0.5 12 --hp 1 --gen2 0
run volley_0.5_hp /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/volleyballgameL_1920x1080_422_10.yuv 1920 1080 0.5 12 --hp 1 --gen2 0
run spot_0.5_hp /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 0.5 12 --hp 1 --gen2 0
run cut_0.5 x 1920 1080 0.5 12 --frames mk_cut
run mixed_0.5 x 1920 1080 0.5 12 --frames mk_mixed
wait

run(){ tag=$1; shift; a1=$1;a2=$2;a3=$3;a4=$4;a5=$5; shift 5; ( TABLES=../out/tables_B.pkl timeout 40000 nice -n 19 python3 run2.py $a1 $a2 $a3 $a4 $a5 $tag "$@" > ../out/r2/log/$tag.txt 2>&1; echo rc=$? >> ../out/r2/log/$tag.txt ) & }
run dng720_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv 1280 720 0.5 12 --S 4
run dng720_1.0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv 1280 720 1.0 12 --S 4
run dng1080_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv 1920 1080 0.5 12
run dng1080_1.0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv 1920 1080 1.0 12
run spot_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 0.5 12
run spot_1.0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 1.0 12
run floor_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/floorballgameL_1920x1080_422_10.yuv 1920 1080 0.5 12
run floor_1.0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/floorballgameL_1920x1080_422_10.yuv 1920 1080 1.0 12
run volley_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/volleyballgameL_1920x1080_422_10.yuv 1920 1080 0.5 12
run volley_1.0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/volleyballgameL_1920x1080_422_10.yuv 1920 1080 1.0 12
run hwy_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/highwaydriveL_1920x1080_422_10.yuv 1920 1080 0.5 12
run hwy_1.0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/highwaydriveL_1920x1080_422_10.yuv 1920 1080 1.0 12
run gfx_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv 448 256 0.5 12
run gfx_1.0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv 448 256 1.0 12
wait

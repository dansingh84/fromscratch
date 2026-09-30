run(){ tag=$1; shift; a1=$1;a2=$2;a3=$3;a4=$4;a5=$5; shift 5; ( TABLES=${TB:-../out/tables_B.pkl} timeout 40000 nice -n 19 python3 run2.py $a1 $a2 $a3 $a4 $a5 $tag "$@" > ../out/r2/log/$tag.txt 2>&1; echo rc=$? >> ../out/r2/log/$tag.txt ) & }
run f420_0.5 ../out/r2/src_dng1080_420_10.yuv 1920 1080 0.5 6 --fmt 420
run f444_12_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_444_12.yuv 1920 1080 0.5 6 --fmt 444 --depth 12
run f422_8_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_8.yuv 1920 1080 0.5 6 --depth 8
run f422_12_0.5 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_12.yuv 1920 1080 0.5 6 --depth 12
run lim_0.5 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/dngL_1920x1080_422_10.yuv 1920 1080 0.5 4 --rng 64,940,64,960
run cut24_0.5 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/cut24.yuv 256 64 0.5 12
run cut24_1.0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/cut24.yuv 256 64 1.0 12
run ext10_1.0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_10_422_l0.yuv 512 128 1.0 4
run ext10L_1.0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_10_422_l1.yuv 512 128 1.0 4 --rng 64,940,64,960
run ext8_1.0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_8_422_l0.yuv 512 128 1.0 4 --depth 8
run ext12_1.0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_12_422_l0.yuv 512 128 1.0 4 --depth 12
run ext12_444_1.0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_12_444_l0.yuv 512 128 1.0 4 --depth 12 --fmt 444
wait

cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/exE
python3 ../notes/exact_e.py gfx_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv 448 256 0 > gfx.log 2>&1 &
python3 ../notes/exact_e.py dng720_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv 1280 720 0 > dng720.log 2>&1 &
python3 ../notes/exact_e.py dng1080_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv 1920 1080 0 > dng1080.log 2>&1 &
python3 ../notes/exact_e.py spot_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 0 > spot.log 2>&1 &
python3 ../notes/exact_e.py cut24_f0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/cut24.yuv 256 64 0 0.5 > cut24.log 2>&1 &
python3 ../notes/exact_e.py extFULL_f0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_10_422_l0.yuv 512 128 0 0.5 > ext.log 2>&1 &
wait; echo DONE > E.done

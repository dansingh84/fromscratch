cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/vc
python3 ../notes/vcausal.py gfx_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv 448 256 0 8 B co > gfx_f0.Bco.log 2>&1 &
python3 ../notes/vcausal.py gfx_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv 448 256 0 8 Bbase > gfx_f0.Bbase.log 2>&1 &
python3 ../notes/vcausal.py dng720_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv 1280 720 0 8 B co > dng720_f0.Bco.log 2>&1 &
python3 ../notes/vcausal.py dng720_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv 1280 720 0 8 Bbase > dng720_f0.Bbase.log 2>&1 &
python3 ../notes/vcausal.py dng1080_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv 1920 1080 0 16 B co > dng1080_f0.Bco.log 2>&1 &
python3 ../notes/vcausal.py dng1080_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv 1920 1080 0 16 Bbase > dng1080_f0.Bbase.log 2>&1 &
python3 ../notes/vcausal.py city_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cityalley_1920x1080_422_10.yuv 1920 1080 0 16 B co > city_f0.Bco.log 2>&1 &
python3 ../notes/vcausal.py city_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cityalley_1920x1080_422_10.yuv 1920 1080 0 16 Bbase > city_f0.Bbase.log 2>&1 &
python3 ../notes/vcausal.py spot_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 0 16 B co > spot_f0.Bco.log 2>&1 &
python3 ../notes/vcausal.py spot_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 0 16 Bbase > spot_f0.Bbase.log 2>&1 &
wait; echo DONE > B.done

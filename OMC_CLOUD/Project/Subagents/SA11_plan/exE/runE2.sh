cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/exE
export E_VARS=E1q,E2qK1 E_SUFFIX=.q
python3 ../notes/exact_e.py gfx_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv 448 256 0 > q_gfx.log 2>&1 &
python3 ../notes/exact_e.py dng720_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv 1280 720 0 > q_dng720.log 2>&1 &
python3 ../notes/exact_e.py dng1080_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv 1920 1080 0 > q_dng1080.log 2>&1 &
python3 ../notes/exact_e.py spot_f0 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 0 > q_spot.log 2>&1 &
python3 ../notes/exact_e.py cut24_f0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/cut24.yuv 256 64 0 0.5,1.0,2.0 > q_cut24.log 2>&1 &
python3 ../notes/exact_e.py extFULL_f0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_10_422_l0.yuv 512 128 0 0.5,1.0,2.0 > q_ext.log 2>&1 &
E_VARS=E1,E1q,E2qK1,E2qK4,E3 E_SUFFIX=.r0zero E_R0=zero python3 ../notes/exact_e.py extFULL_f0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_10_422_l0.yuv 512 128 0 0.5,1.0,2.0 > r0z.log 2>&1 &
E_VARS=E1,E1q,E2qK1,E2qK4,E3 E_SUFFIX=.r0first E_R0=first python3 ../notes/exact_e.py extFULL_f0 /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_10_422_l0.yuv 512 128 0 0.5,1.0,2.0 > r0f.log 2>&1 &
wait; echo DONE > E2.done

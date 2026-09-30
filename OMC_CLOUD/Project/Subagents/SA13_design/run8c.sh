#!/bin/bash
A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
SCR=/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA13_design
# (a) still input: frame 0 repeated 16 frames, dng 720p S=8
o=$SCR/still720.yuv
nice -n 19 python3 t8_inter.py $A/dng_1280x720_422_10.yuv 1280 720 422 16 STILL_dng720_D56 8 56 --still --out $o || echo FAIL still
python3 - $o <<'PY'
import numpy as np, sys
d=np.fromfile(sys.argv[1],dtype='<u2').reshape(16,-1).astype(int)
print('STILL changed-sample fraction per frame pair (all planes):', ' '.join('%.4f'%((d[f]!=d[f-1]).mean()) for f in range(1,16)))
PY
python3 /home/user/fromscratch/OMC_CLOUD/Project/.work/v537/tests/ants.py $o.src $o 1280 720 422 10 || echo FAIL ants
rm -f $o $o.src
# (b) intra every frame (P=1) vs inter, same toy, dng1080 D=36
o=$SCR/p1.yuv
nice -n 19 python3 t8_inter.py $A/dng_1920x1080_422_10.yuv 1920 1080 422 12 INTRA_dng1080_D36 16 36 --P 1 --out $o || echo FAIL p1
python3 eval_dec.py $A/dng_1920x1080_422_10.yuv $o 1920 1080 12 16 INTRA_dng1080_D36; rm -f $o
# (c) narrower dead zone (dz 0.75), dng1080 S16 D48
o=$SCR/dz.yuv
nice -n 19 python3 t8_inter.py $A/dng_1920x1080_422_10.yuv 1920 1080 422 12 DZ75_dng1080_D48 16 48 --dz 0.75 --out $o || echo FAIL dz
python3 eval_dec.py $A/dng_1920x1080_422_10.yuv $o 1920 1080 12 16 DZ75_dng1080_D48; rm -f $o
# (d) floor rounding (cast control), dng720 D56
nice -n 19 python3 t8_inter.py $A/dng_1280x720_422_10.yuv 1280 720 422 12 FLOOR_dng720_D56 8 56 --round floor || echo FAIL floor

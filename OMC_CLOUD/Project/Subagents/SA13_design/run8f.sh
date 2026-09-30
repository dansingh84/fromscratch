#!/bin/bash
A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA13_design
until ! pgrep -f "SRCMV_" >/dev/null; do sleep 20; done
for am in 4.5 6; do AM=$am nice -n 19 python3 t8_inter.py $A/dng_1920x1080_422_10.yuv 1920 1080 422 10 AM${am}_dng1080 8 36 --dzi 1.25 --lam 1 | cut -c1-600; done

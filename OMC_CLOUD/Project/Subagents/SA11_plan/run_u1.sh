#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan
export OMC_R1_REUSE=1
U=../SA7_legality_v2/rtree4/notes/u.sh
bash $U gfx8_05 448 256 422 10 0.5 8 run1 lists/gfx8_05.txt
bash $U spot_10 1920 1080 422 10 1.0 1 run1 lists/spot_10.txt
bash $U d7x8_05 1280 720 422 10 0.5 8 run1 lists/d7x8_05.txt
echo U1DONE

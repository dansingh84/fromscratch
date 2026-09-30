#!/bin/bash
# H11/H12: G-b test, reference-only inter prediction (ALPHA=0), 3 test clips at 0.5/1.0/2.0, frame 2 vs today
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design/bench/t1
[ -f t1core.so ] || gcc -O2 -shared -fPIC -o t1core.so t1core.c -lm
mkdir -p ../../out/gb
ALPHA=0 CLIPS=cine_A005C031,gfx444_B001C001,prores_sample RATES=0.5,1.0,2.0 python3 t1_seq.py > ../../out/gb/alpha0_test.txt 2>&1

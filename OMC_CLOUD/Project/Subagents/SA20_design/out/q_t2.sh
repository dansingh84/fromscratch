#!/bin/bash
# G81: T2 intra screen on the 3 test clips at 0.5 / 1.0 (step grid 1/16 octave): D x KA x ALPHA x RHO
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design/t1; mkdir -p ../out/t2
run() { D=$1 KA=$2 ALPHA=$3 RHO=$4 python3 t2_intra.py > ../out/t2/D$1_KA$2_A$3_rho$4.txt 2>&1; }
for cfg in "4 0.5 0.5 0.42" "4 0.5 0.25 0.42" "4 0.5 0.75 0.42" "4 0.35 0.5 0.42" "4 0.7 0.5 0.42" "8 0.5 0.5 0.42" "8 0.35 0.5 0.42" "4 0.5 0.5 0.3" "2 0.5 0.5 0.42"; do
  run $cfg & while [ $(pgrep -fc t2_intra.py) -ge 3 ]; do sleep 10; done
done; wait

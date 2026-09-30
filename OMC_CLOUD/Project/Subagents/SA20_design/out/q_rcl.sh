#!/bin/bash
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design
for c in gfx444_F003C012 cine_4k_A006 cine_A005C021 gfx444_B001C001; do
  while [ $(ps -eo args | grep -c "^python3 bench/rcl_") -ge 5 ]; do sleep 60; done
  RCL=1 RHO=0.42 nice -n 5 python3 bench/rcl_s16.py $c 1 S16 > out/rcl_s16/rclamp_$c.log 2>&1 < /dev/null &
  sleep 5
done; wait
SP=/tmp/claude-0/-home-user-fromscratch/ca3365f6-68f7-5957-a3a2-a3df5f0ee7ba/scratchpad
for f in out/rcl_s16/rclamp_*.log; do b=$(basename $f .log); sed "s/_S16 /_S16rclamp /" $f > $SP/$b.log; done
python3 bench/intra_vs_today.py $SP/rclamp_*.log > out/rclamp_vs_today.txt 2>&1

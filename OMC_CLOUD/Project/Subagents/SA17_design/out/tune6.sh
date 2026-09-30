cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
T=../out/tab_eb_r2.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0"
nice python3 tune.py $T hold2 city,traffic,winter 0.5 $P still_hold=2 >> ../out/tune6.log 2>&1 &
nice python3 stilltest.py $T frozen 0.5 12 $P still_hold=2 > ../out/still_frozen_h2mode.log 2>&1 &
MY=40 MX=160 nice python3 stilltest.py $T mixed 0.5 12 $P still_hold=2 > ../out/still_mixed_h2mode.log 2>&1 &
wait; echo DONE >> ../out/tune6.log

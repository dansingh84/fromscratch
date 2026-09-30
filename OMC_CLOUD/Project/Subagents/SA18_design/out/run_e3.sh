cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
T=../out/tab_h_r1.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
export SA18_BANK="-0.5,-0.25,0,0.25,0.5,1,1.5,2"
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && (/evalcell.py/ || /stilltest.py/)' | wc -l) -ge 6 ]; do sleep 10; done; "$@" & sleep 2; }
run nice -n 19 python3 evalcell.py volley 0.5 pair $T ev359 $P events=3:5:9 > ../out/e3_ev_volley.log 2>&1
run nice -n 19 python3 evalcell.py dng720 0.5 pair $T ev359 $P S=4 events=3:5:9 > ../out/e3_ev_dng720.log 2>&1
run nice -n 19 python3 evalcell.py dng720 0.5 pair $T bank $P S=4 > ../out/e3_bank_dng720.log 2>&1
run nice -n 19 python3 stilltest.py $T frozen 0.5 12 tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1 events=3:5:9 > ../out/e3_still_frozen_ev.log 2>&1
wait

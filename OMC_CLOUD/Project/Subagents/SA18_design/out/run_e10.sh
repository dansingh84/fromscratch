cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
T=../out/tab_h_r1.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && (/evalcell.py/ || /stilltest.py/ || /chain18.py/ || /train_part.py/)' | wc -l) -ge 7 ]; do sleep 10; done; "$@" & sleep 2; }
run nice -n 19 python3 evalcell.py hwy 0.5 pair $T C1nobank $P ccv=2 > ../out/e10_nobank_hwy.log 2>&1
run nice -n 19 python3 evalcell.py volley 0.5 pair $T C1nobank $P ccv=2 > ../out/e10_nobank_volley.log 2>&1
wait

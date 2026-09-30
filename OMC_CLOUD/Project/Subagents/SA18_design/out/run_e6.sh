cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
T=../out/tab_h_r1.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1 S=4"
export SA18_BANK="-0.5,-0.25,0,0.25,0.5,1,1.5,2"
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && (/evalcell.py/ || /stilltest.py/ || /chain18.py/)' | wc -l) -ge 6 ]; do sleep 10; done; "$@" & sleep 2; }
run nice -n 19 python3 evalcell.py dng720 0.5 pair $T ea2 $P ccv=2 eages=2 > ../out/e6_ea2.log 2>&1
run nice -n 19 python3 evalcell.py dng720 0.5 pair $T ea24 $P ccv=2 eages=2:4 > ../out/e6_ea24.log 2>&1
run nice -n 19 python3 evalcell.py dng720 0.5 pair $T ea1 $P ccv=2 eages=1 > ../out/e6_ea1.log 2>&1
run nice -n 19 python3 evalcell.py dng720 0.5 pair $T ea26 $P ccv=2 eages=2:6 > ../out/e6_ea26.log 2>&1
wait

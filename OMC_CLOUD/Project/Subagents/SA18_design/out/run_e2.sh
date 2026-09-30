cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
T=../out/tab_h_r1.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
BK="-0.5,-0.25,0,0.25,0.5,1,1.5,2"
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && /evalcell.py/' | wc -l) -ge 6 ]; do sleep 10; done; "$@" & sleep 2; }
for c in volley hwy floor dng720; do
  S=""; [ $c = dng720 ] && S="S=4"
  run env nice -n 19 python3 evalcell.py $c 0.5 pair $T ccv $P $S ccv=1 > ../out/e2_ccv_${c}.log 2>&1
  run env SA18_BANK=$BK nice -n 19 python3 evalcell.py $c 0.5 pair $T bank $P $S > ../out/e2_bank_${c}.log 2>&1
  run env SA18_BANK=$BK nice -n 19 python3 evalcell.py $c 0.5 pair $T ccvbank $P $S ccv=1 > ../out/e2_ccvbank_${c}.log 2>&1
done
wait

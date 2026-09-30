cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
T=../out/tab_h_r1.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
export SA18_BANK="-0.5,-0.25,0,0.25,0.5,1,1.5,2"
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && (/evalcell.py/ || /stilltest.py/)' | wc -l) -ge 6 ]; do sleep 10; done; "$@" & sleep 2; }
sleep 60
for c in hwy floor volley dng720; do S=""; [ $c = dng720 ] && S="S=4"
  run nice -n 19 python3 evalcell.py $c 0.5 pair $T cfv2bank $P $S ccv=2 > ../out/e4_cfv2bank_${c}.log 2>&1
done
wait

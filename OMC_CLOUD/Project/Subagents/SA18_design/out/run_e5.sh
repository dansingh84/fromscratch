cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
T=../out/tab_h_r1.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
export SA18_BANK="-0.5,-0.25,0,0.25,0.5,1,1.5,2"
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && (/evalcell.py/ || /stilltest.py/ || /chain18.py/)' | wc -l) -ge 6 ]; do sleep 10; done; "$@" & sleep 2; }
for c in volley dng720 hwy floor; do S=""; [ $c = dng720 ] && S="S=4"
  run nice -n 19 python3 evalcell.py $c 0.5 pair $T C2 $P $S ccv=2 eages=2:4:8 > ../out/e5_C2_${c}_0.5.log 2>&1
  run nice -n 19 python3 evalcell.py $c 0.5 pair $T C1 $P $S ccv=2 > ../out/e5_C1_${c}_0.5.log 2>&1
done
run nice -n 19 python3 stilltest.py $T mixed 0.5 12 tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1 eages=2:4:8 ccv=2 > ../out/e5_still_mixed_C2.log 2>&1
run env MY=40 MX=160 nice -n 19 python3 stilltest.py $T mixed 0.5 12 tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1 eages=2:4:8 ccv=2 > ../out/e5_still_mixedwide_C2.log 2>&1
wait

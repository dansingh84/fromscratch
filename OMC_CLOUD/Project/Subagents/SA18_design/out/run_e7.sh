cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
T=../out/tab_h_r1.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
export SA18_BANK="-0.5,-0.25,0,0.25,0.5,1,1.5,2"
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && (/evalcell.py/ || /stilltest.py/ || /chain18.py/)' | wc -l) -ge 7 ]; do sleep 10; done; "$@" & sleep 2; }
for t in 2 4; do
  run nice -n 19 python3 stilltest.py $T frozen 0.5 12 $P ccv=2 habs=$t noisek=1.5 > ../out/e7_frozen_h$t.log 2>&1
  run env MY=40 MX=160 nice -n 19 python3 stilltest.py $T mixed 0.5 12 $P ccv=2 habs=$t noisek=1.5 > ../out/e7_mixed_h$t.log 2>&1
  run nice -n 19 python3 evalcell.py dng720 0.5 pair $T C3h$t $P S=4 ccv=2 habs=$t noisek=1.5 > ../out/e7_C3h${t}_dng720.log 2>&1
  run nice -n 19 python3 evalcell.py volley 0.5 pair $T C3h$t $P ccv=2 habs=$t noisek=1.5 > ../out/e7_C3h${t}_volley.log 2>&1
done
run nice -n 19 python3 stilltest.py $T frozen 0.5 12 $P ccv=2 > ../out/e7_frozen_C1.log 2>&1
wait

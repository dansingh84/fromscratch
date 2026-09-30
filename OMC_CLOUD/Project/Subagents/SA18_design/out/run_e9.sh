cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
T=../out/tab_h_r1.pkl; P="rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
export SA18_BANK="-0.5,-0.25,0,0.25,0.5,1,1.5,2"
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && (/evalcell.py/ || /stilltest.py/ || /chain18.py/ || /train_part.py/)' | wc -l) -ge 7 ]; do sleep 10; done; "$@" & sleep 2; }
for t in 0.25 0.5 0.75; do
  run nice -n 19 python3 evalcell.py city 0.5 pair $T tilt$t $P tilt=$t ccv=2 > ../out/e9_tilt${t}_city.log 2>&1
done
wait

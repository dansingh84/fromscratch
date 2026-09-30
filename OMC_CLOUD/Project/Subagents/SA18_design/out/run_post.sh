cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
until [ -f ../out/final_done ]; do sleep 30; done
T=../out/tab_f1.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && (/evalcell.py/ || /stilltest.py/ || /chain18.py/ || /heal18.py/ || /oneway18.py/)' | wc -l) -ge 6 ]; do sleep 10; done; "$@" & sleep 2; }
run nice -n 19 python3 evalcell.py city 0.5 pair ../out/tab_h_r1.pkl tilt0 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1 tilt=0 ccv=2 > ../out/e9_tilt0_city.log 2>&1
run env TABS=$T RECOFF=2 nice -n 19 python3 chain18.py dng720 0.5 8 > ../out/chain_dng720.log 2>&1
run env TABS=$T RECOFF=2 nice -n 19 python3 chain18.py spot 0.5 6 > ../out/chain_spot.log 2>&1
run nice -n 19 python3 heal18.py dng720 0.5 $T 2 4 40 > ../out/heal_dng720_rt2.log 2>&1
run nice -n 19 python3 heal18.py volley 0.5 $T 2 4 60 8 > ../out/heal_volley_rt2_8sl.log 2>&1
run nice -n 19 python3 oneway18.py dng720 0.5 $T 2 4 40 > ../out/oneway_dng720_c2.log 2>&1
run nice -n 19 python3 stilltest.py $T frozen 0.5 12 $P ccv=2 > ../out/still_frozen.log 2>&1
run env MY=40 MX=160 nice -n 19 python3 stilltest.py $T mixed 0.5 12 $P ccv=2 > ../out/still_mixed_wide.log 2>&1
wait
bash ../out/art18.sh final
echo DONE > ../out/post_done

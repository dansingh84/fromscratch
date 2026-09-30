cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
until grep -q DONE ../out/eval_final.log; do sleep 30; done
T=../out/tab_eb_r2.pkl
for t0 in 3 4; do nice python3 oneway.py dng720 0.5 $T 2 $t0 80 > ../out/oneway_c2_t$t0.log 2>&1 & done
nice python3 oneway.py dng720 0.5 $T 3 4 80 > ../out/oneway_c3_t4.log 2>&1 &
nice python3 oneway.py dng720 0.5 $T 3 5 80 > ../out/oneway_c3_t5.log 2>&1 &
wait
P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=1 cycle=2 still_hold=1"
run(){ while [ $(jobs -r | wc -l) -ge 6 ]; do sleep 5; done; nice python3 evalcell.py "$@" >> ../out/eval_oneway.log 2>&1 & }
for c in dng720 dng1080 spot floor hwy volley; do for b in 0.5 1.0; do
  S=""; [ $c = dng720 ] && S="S=4"
  run $c $b pair $T ow2 $P $S
done; done
wait; echo DONE >> ../out/eval_oneway.log

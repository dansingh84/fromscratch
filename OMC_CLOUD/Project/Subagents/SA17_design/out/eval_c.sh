cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
T=../out/tab_eb_r2.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
run(){ while [ $(jobs -r | wc -l) -ge 6 ]; do sleep 5; done; nice python3 evalcell.py "$@" >> ../out/eval_c.log 2>&1 & }
for c in dng720 dng1080 spot floor hwy volley; do for b in 0.5 1.0; do
  S=""; [ $c = dng720 ] && S="S=4"
  run $c $b pair $T c1 $P $S
done; done
wait
W="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=1 still_hold=1"
for c in dng720 hwy; do for cy in 1 2 3 4 8; do
  S=""; [ $c = dng720 ] && S="S=4"
  while [ $(jobs -r | wc -l) -ge 6 ]; do sleep 5; done
  nice python3 evalcell.py $c 0.5 pair $T wave$cy $W cycle=$cy $S >> ../out/eval_wave.log 2>&1 &
done; done
wait
nice python3 stilltest.py $T mixed 0.5 12 tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1 > ../out/still_mixed_h2.log 2>&1
echo DONE >> ../out/eval_c.log

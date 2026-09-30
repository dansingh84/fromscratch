cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
T=../out/tab_f1.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1 ccv=2 recoff=2"
unset SA18_BANK
run(){ while [ $(ps -eo comm,args | awk '$1=="python3" && (/evalcell.py/ || /stilltest.py/ || /chain18.py/)' | wc -l) -ge 6 ]; do sleep 10; done; "$@" & sleep 2; }
for b in 0.5 1.0; do for c in dng720 dng1080 spot floor hwy volley; do S=""; [ $c = dng720 ] && S="S=4"
  run nice -n 19 python3 evalcell.py $c $b pair $T final $P $S > ../out/final_${c}_$b.log 2>&1
done; done
wait
echo DONE > ../out/final_done

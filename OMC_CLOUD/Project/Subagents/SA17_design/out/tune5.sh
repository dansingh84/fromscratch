cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
until grep -q DONE ../out/eval_c.log; do sleep 30; done
T=../out/tab_eb_r2.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0"
run(){ nice python3 tune.py $T "$1" traffic,winter,city 0.5 $P ${@:2} >> ../out/tune5.log 2>&1; }
run hold1 still_hold=1 &
run hold0 still_hold=0 &
run hold1r30 still_hold=1 rho=0.30 &
wait
echo DONE >> ../out/tune5.log

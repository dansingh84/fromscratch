cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
T=../out/tab_eb_r2.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4 refresh=0 still_hold=1"
run(){ while [ $(jobs -r | wc -l) -ge 5 ]; do sleep 5; done; nice python3 tune.py $T "$1" traffic,winter,ftrain,hview 0.5 $P ${@:2} >> ../out/tune7.log 2>&1 & }
run base
run ry8 ry=8
run ztol1 ztol=1
run ztol0 ztol=0
run l1k05 l1k=0.5
run l1k1 l1k=1.0
run l1k2 l1k=2.0
wait; echo DONE >> ../out/tune7.log

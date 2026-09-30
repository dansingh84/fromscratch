cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
T=../out/tab_seq_pair.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4"
run(){ nice python3 tune.py $T "$1" traffic,winter 0.5 $P ${@:2} >> ../out/tune3.log 2>&1; }
run base &
run cyc12 cycle=12 &
run cyc16 cycle=16 &
wait

cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
T=../out/tab_seq_pair.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4"
run(){ nice python3 tune.py $T "$1" traffic,winter 0.5 $P ${@:2} >> ../out/tune4.log 2>&1; }
run base_ext &
run cyc12_ext cycle=12 &
run noclean clean=0 &
wait

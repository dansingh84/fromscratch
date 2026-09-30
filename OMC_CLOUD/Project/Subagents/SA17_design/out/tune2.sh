cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
T=../out/tab_seq_pair.pkl
run(){ nice python3 tune.py $T "$1" city,traffic,winter 0.5,1.0 ${@:2} >> ../out/tune2.log 2>&1; }
run t25 tilt=0.25 &
run t25r35 tilt=0.25 rho=0.35 &
run t25r30 tilt=0.25 rho=0.30 &
run t375r35 tilt=0.375 rho=0.35 &
run t25r35lam4 tilt=0.25 rho=0.35 lam=4 &
run t25r35b64 tilt=0.25 rho=0.35 bx=64 lam=4 &
wait
run t25r35c5 tilt=0.25 rho=0.35 chroma=0.5 &
run t25r35cm5 tilt=0.25 rho=0.35 chroma=-0.5 &
run t25r35s2 tilt=0.25 rho=0.35 rho_still=0.2 &
wait

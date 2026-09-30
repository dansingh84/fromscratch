cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
T=../out/tab_seq_pair_r0.pkl
run(){ nice python3 tune.py $T "$1" city,traffic 0.5,1.0 $2 $3 $4 >> ../out/tune1.log 2>&1; }
run base tilt=0 &
run tiltp25 tilt=0.25 &
run tiltm25 tilt=-0.25 &
wait
run tiltp5 tilt=0.5 &
run rho35 rho=0.35 &
run rho50 rho=0.5 &
wait
run chm5 chroma=-0.5 &
run chp5 chroma=0.5 &
wait

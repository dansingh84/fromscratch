cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
T=../out/tab_seq_pair.pkl; P="tilt=0.25 rho=0.35 bx=64 lam=4"
ev(){ nice python3 evalcell.py $1 $2 pair $T a1 $P $3 >> ../out/eval_a1.log 2>&1; }
ev dng720 0.5 S=4 & ev dng720 1.0 S=4 & ev dng1080 0.5 & ev dng1080 1.0 & ev spot 0.5 & ev spot 1.0 &
wait
ev floor 0.5 & ev floor 1.0 & ev hwy 0.5 & ev hwy 1.0 & ev volley 0.5 & ev volley 1.0 &
wait

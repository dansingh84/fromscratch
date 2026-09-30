cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
P="tilt=0.25 rho=0.35 bx=64 lam=4"
nice python3 evalcell.py hwy 0.5 pair ../out/tab_seq_pair.pkl b_norefresh $P refresh=0 >> ../out/eval_b.log 2>&1 &
nice python3 evalcell.py floor 0.5 pair ../out/tab_seq_pair.pkl b_norefresh $P refresh=0 >> ../out/eval_b.log 2>&1 &
nice python3 evalcell.py hwy 0.5 53 ../out/tab_seq_53.pkl b_53 $P >> ../out/eval_b.log 2>&1 &
nice python3 evalcell.py floor 0.5 53 ../out/tab_seq_53.pkl b_53 $P >> ../out/eval_b.log 2>&1 &
wait

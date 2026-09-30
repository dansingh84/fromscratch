cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
nice python3 train.py ../out/tab_intra_53.pkl 53 2 > ../out/train_intra_53.log 2>&1 && \
nice python3 train_seq.py ../out/tab_seq_53.pkl 53 2 ../out/tab_intra_53.pkl > ../out/train_seq_53.log 2>&1

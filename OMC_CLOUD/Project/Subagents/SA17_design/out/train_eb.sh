cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/model
START=../out/tab_seq_pair.pkl
for r in 1 2; do
  ls ../out/cnt_r$r_* 2>/dev/null
  for cl in bos city rsg traffic winter; do
    for b in 0.5 1.0 2.0; do
      while [ $(jobs -r | wc -l) -ge 6 ]; do sleep 5; done
      nice python3 train_part.py $cl $b $START ../out/cnt_r${r}_${cl}_$b.pkl >> ../out/train_eb.log 2>&1 &
    done
  done
  wait
  python3 train_merge.py ../out/tab_eb_r$r.pkl ../out/cnt_r${r}_*.pkl >> ../out/train_eb.log 2>&1
  START=../out/tab_eb_r$r.pkl
done
echo DONE >> ../out/train_eb.log

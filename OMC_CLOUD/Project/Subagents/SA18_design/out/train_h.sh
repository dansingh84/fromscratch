cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
START=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/tab_eb_r2.pkl
for r in 1 2; do
  for cl in bos city rsg traffic winter; do
    for b in 0.5 1.0 2.0; do
      while [ $(jobs -r | wc -l) -ge 4 ]; do sleep 5; done
      nice -n 19 python3 train_part.py $cl $b $START ../out/cnth_r${r}_${cl}_$b.pkl still_hold=1 >> ../out/train_h.log 2>&1 &
    done
  done
  wait
  python3 train_merge.py ../out/tab_h_r$r.pkl ../out/cnth_r${r}_*.pkl >> ../out/train_h.log 2>&1
  START=../out/tab_h_r$r.pkl
done
echo DONE >> ../out/train_h.log

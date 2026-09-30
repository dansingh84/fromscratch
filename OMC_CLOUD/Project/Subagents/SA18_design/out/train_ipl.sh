cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
export SA18_XF=ipl
START=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/tab_eb_r2.pkl
for r in 1 2; do
  for cl in bos city rsg traffic winter; do
    for b in 0.5 1.0 2.0; do
      while [ $(pgrep -fc "train_(part|intra).py") -ge 6 ]; do sleep 5; done
      nice -n 19 python3 train_intra.py $cl $b $START ../out/cnti_r${r}_${cl}_$b.pkl >> ../out/train_ipl.log 2>&1 &
      sleep 1
    done
  done
  wait
  python3 train_merge.py ../out/tab_ipl_r$r.pkl ../out/cnti_r${r}_*.pkl >> ../out/train_ipl.log 2>&1
  START=../out/tab_ipl_r$r.pkl
done
echo DONE >> ../out/train_ipl.log

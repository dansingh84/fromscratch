cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
unset SA18_BANK
START=../out/tab_f1.pkl
for cl in bos city rsg traffic winter; do
  for b in 0.5 1.0 2.0; do
    while [ $(ps -eo comm,args | awk '$1=="python3" && (/train_part.py/ || /evalcell.py/ || /chain18.py/ || /stilltest.py/)' | wc -l) -ge 11 ]; do sleep 10; done
    nice -n 19 python3 train_part.py $cl $b $START ../out/cntf2_${cl}_$b.pkl still_hold=1 ccv=2 recoff=2 >> ../out/train_f2.log 2>&1 &
    sleep 2
  done
done
wait
python3 train_merge.py ../out/tab_f2.pkl ../out/cntf2_*.pkl >> ../out/train_f2.log 2>&1
echo DONE >> ../out/train_f2.log

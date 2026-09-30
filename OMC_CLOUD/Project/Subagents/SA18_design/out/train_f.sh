cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA18_design/bench
export SA18_BANK="-0.5,-0.25,0,0.25,0.5,1,1.5,2"
START=../out/tab_h_r1.pkl
for cl in bos city rsg traffic winter; do
  for b in 0.5 1.0 2.0; do
    while [ $(ps -eo comm,args | awk '$1=="python3" && (/train_part.py/ || /evalcell.py/ || /chain18.py/ || /stilltest.py/)' | wc -l) -ge 6 ]; do sleep 10; done
    nice -n 19 python3 train_part.py $cl $b $START ../out/cntf_r1_${cl}_$b.pkl still_hold=1 ccv=2 >> ../out/train_f.log 2>&1 &
    sleep 2
  done
done
wait
python3 train_merge.py ../out/tab_f1.pkl ../out/cntf_r1_*.pkl >> ../out/train_f.log 2>&1
echo DONE >> ../out/train_f.log

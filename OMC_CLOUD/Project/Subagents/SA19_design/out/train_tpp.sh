# usage: train_tpp.sh ARM START "args"   -> counts cnt_ARM_*.pkl, tables tab_ARM.pkl
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA19_design/bench
ARM=$1; START=$2; ARGS=$3
mine(){ ps -eo args | grep -E '^python3 (tpp_run|s1_|evalcell)' | grep -v grep | wc -l; }
for cl in bos city rsg traffic winter; do for b in 0.5 1.0; do
  while [ $(ps -eo pid,args | awk '/python3 tpp_run.py/ && !/awk/' | while read p a; do readlink /proc/$p/cwd; done | grep -c SA19_design) -ge 6 ]; do sleep 10; done
  nice -n 19 python3 tpp_run.py train $cl $b $START ../out/cnt_${ARM}_${cl}_$b.pkl $ARGS >> ../out/train_$ARM.log 2>&1 &
  sleep 3
done; done
wait
python3 train_merge.py ../out/tab_$ARM.pkl ../out/cnt_${ARM}_*.pkl >> ../out/train_$ARM.log 2>&1
echo DONE >> ../out/train_$ARM.log

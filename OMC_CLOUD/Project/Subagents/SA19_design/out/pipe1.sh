cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA19_design/out
until grep -q DONE train_f0.log 2>/dev/null && grep -q DONE train_f1.log 2>/dev/null; do sleep 30; done
: > q_ev1.txt
for b in 0.5 1.0; do for c in dng720 dng1080 spot floor hwy volley; do
 echo "nice -n 19 python3 tpp_run.py eval $c $b ../out/tab_f0.pkl A0 fuse=0 > ../out/ev_A0_${c}_$b.log 2>&1" >> q_ev1.txt
 echo "nice -n 19 python3 tpp_run.py eval $c $b ../out/tab_f1.pkl A1 fuse=1 wf=8 > ../out/ev_A1_${c}_$b.log 2>&1" >> q_ev1.txt
done; done
bash q.sh q_ev1.txt &
./train_tpp.sh f2 ../out/tab_f1.pkl "fuse=1 wk=1" &
./train_tpp.sh c0 ../out/tab_f0.pkl "fuse=0 still=catch" &
wait

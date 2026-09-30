# arm.sh ARM START "args" "evalcells(cell:bpp ...)"  : train 3 disjoint clips x 0.5/1.0 on the exact config, merge, eval
O=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA19_design/out; cd $O
ARM=$1; START=$2; ARGS=$3; CELLS=$4; ENVP=$5
: > $O/qt_$ARM.txt
for cl in bos city traffic; do for b in 0.5 1.0; do
 echo "$ENVP nice -n 19 python3 tpp_run.py train $cl $b $START ../out/cnt_${ARM}_${cl}_$b.pkl $ARGS >> ../out/train_$ARM.log 2>&1" >> $O/qt_$ARM.txt
done; done
bash q.sh $O/qt_$ARM.txt
cd ../bench; python3 train_merge.py ../out/tab_$ARM.pkl ../out/cnt_${ARM}_*.pkl >> ../out/train_$ARM.log 2>&1; cd $O
: > $O/qe_$ARM.txt
for cb in $CELLS; do c=${cb%:*}; b=${cb#*:}
 echo "$ENVP nice -n 19 python3 tpp_run.py eval $c $b ../out/tab_$ARM.pkl $ARM $ARGS > ../out/ev_${ARM}_${c}_$b.log 2>&1" >> $O/qe_$ARM.txt
done
bash q.sh $O/qe_$ARM.txt
echo DONE >> $O/train_$ARM.log

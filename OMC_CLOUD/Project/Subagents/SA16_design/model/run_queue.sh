#!/bin/bash
# evaluation queue: cells x rates with bounded parallelism; row-phase stats + renders after each decode.
# usage: run_queue.sh TABLES NPAR cell:rate cell:rate ...
set -u
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model
TAB=$1; NPAR=$2; shift 2
OUT=/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/out; mkdir -p $OUT/eval $OUT/renders
run_one() {
  IFS=: read cell rate <<< "$1"
  nice -n 19 python3 evalcell.py $cell $rate ${NF:-12} $TAB > $OUT/eval/${cell}_${rate}.log 2>&1
  rc=$?; echo "EVAL $cell $rate exit $rc" >> $OUT/eval/queue_status.txt
  if [ $rc -eq 0 ]; then
    python3 - "$cell" "$rate" <<'PY' >> $OUT/eval/${cell}_${rate}.log 2>&1
import sys, subprocess, json
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model'); import yuv, rowphase
cell, rate = sys.argv[1], sys.argv[2]; path, W, H = yuv.CELLS[cell]; S = 4 if H == 720 else 8
OUT = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/out/'
dec = OUT + 'eval/%s_%s.yuv' % (cell, rate); today = yuv.TODAY[cell] % rate
for name, d in (('mine', dec), ('today', today)):
    r = rowphase.stats(path, d, W, H, list(range(2, 12)), S)
    print('ROWPHASE', name, json.dumps({k: {kk: (round(vv, 4) if isinstance(vv, float) else [round(x, 4) for x in vv]) for kk, vv in v.items()} for k, v in r.items()}))
f = 8 if H == 720 else 6
subprocess.run(['python3', 'render.py', path, dec, str(W), str(H), str(f), str(S), OUT + 'renders/%s_%s' % (cell, rate), 'mine'], check=False)
subprocess.run(['python3', 'render.py', path, today, str(W), str(H), str(f), str(S), OUT + 'renders/%s_%s' % (cell, rate), 'today'], check=False)
PY
    rm -f $OUT/eval/${cell}_${rate}.yuv
  fi
}
export -f run_one; export TAB OUT
printf '%s\n' "$@" | xargs -P $NPAR -I{} bash -c 'run_one {}'
echo QUEUE_DONE >> $OUT/eval/queue_status.txt

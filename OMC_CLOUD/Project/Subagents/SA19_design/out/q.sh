# queue runner: runs each line of $1 when fewer than 6 SA19 python jobs are alive
cd /home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA19_design/bench
n(){ for p in $(pgrep -x python3); do readlink /proc/$p/cwd; done 2>/dev/null | grep -c SA19_design; }
while read -r line; do [ -z "$line" ] && continue
  while [ $(n) -ge 6 ]; do sleep 15; done
  bash -c "$line" < /dev/null & sleep 3
done < "$1"
wait

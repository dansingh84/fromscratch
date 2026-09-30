# usage: bash batch.sh LISTFILE  (each line: tag args...) ; runs all lines in parallel
while read -r tag rest; do
  [ -z "$tag" ] && continue
  ( eval "TABLES=\${TB_$tag:-../out/tables_B.pkl} timeout 60000 nice -n 19 python3 run2.py $rest --tag_dummy 0" > /dev/null 2>&1 ) &
done < "$1"; wait

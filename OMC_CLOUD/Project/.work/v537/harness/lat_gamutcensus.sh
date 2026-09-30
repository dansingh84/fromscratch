#!/bin/bash
# [A5-CENSUS] How much out-of-gamut work does the repair face, per arm and per rate?
# Repair OFF isolates the raw excursion population (fast: no repair loop).
set -u
P=/home/user/fromscratch/OMC_CLOUD/Project
G=$P/Agents/Agent5/pin; L=$P/.work/arms/long
export TMPDIR=$P/.work/scratch/tmp
O=$P/Agents/Agent5/out; LOG=$O/gamut_census.log; : > $LOG
echo "# repair OFF (OMC_GAMUT_STRICT=0), 12 frames, enc $(md5sum $G/omc_enc|cut -c1-12)" >>$LOG
echo "# 'excursions' = committed samples outside legal range, encoder's own count" >>$LOG
for c in highwaydrive highwayview officewalk spotrobot trafficlights volleyballgame winterdrive floorballtrain floorballgame; do
  a=$L/${c}L_1920x1080_422_10.yuv; [ -f "$a" ] || continue
  line="  $(printf '%-15s' $c)"
  for b in 0.5 1.0 2.0; do
    n=$(OMC_GAMUT_STRICT=0 $G/omc_enc -i $a -o /dev/null -w 1920 -h 1080 --fmt 422 --depth 10 \
        --bpp $b -n 12 2>&1 >/dev/null | grep -oE "gamut: [0-9]+ committed" | grep -oE "^[0-9]+|[0-9]+" | tail -1)
    line="$line  @$b:$(printf '%8s' ${n:-ERR})"
  done
  echo "$line" >>$LOG
done
echo "CENSUS-DONE $(date)" >>$LOG

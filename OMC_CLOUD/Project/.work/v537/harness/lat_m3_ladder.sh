#!/bin/bash
# [A5-M3] MEMO 016: the R = 2R ladder on the long arms.
#
# Encodes 24 frames from source frame 0, then measures TWO steady-state runs
# (f8-f15, f16-f23) as separate rows.  One encode per (arm,fmt,rate) is reused
# by both windows and by every XS pairing at that OMC rate.
#
# The 8-frame windows are KEPT (small) so the texstat column can be added when
# Agent 2 supplies the instrument, without re-encoding anything.  Full decodes
# are deleted as soon as the windows are cut.
#
# Exit codes are checked at every stage: a failed run must never become a number.
set -u
P=/home/user/fromscratch/OMC_CLOUD/Project
G=$P/Agents/Agent5/pin                    # PINNED binaries (MEMO 017)
SH=$P/.work/sandbox/harness
XSRUN=$P/.work/v54tree_pre55b/harness/xsrun.sh
export XS=$P/.work/tools/SVT-JPEG-XS-main/Bin/Release
export XS_RC=2 XS_SH=32                   # XS at its best (xsrun.sh header)
A=$P/.work/arms/long
O=$P/Agents/Agent5/out/m3
W_DIR=$O/win
export TMPDIR=$P/.work/scratch/tmp; mkdir -p "$TMPDIR" "$W_DIR"
LOG=$O/ladder.log
ENCMD5=$(md5sum $G/omc_enc | cut -c1-12); DECMD5=$(md5sum $G/omc_dec | cut -c1-12)
# The shared tree was rebuilt mid-run once already (2026-09-06 08:12), changing
# encoder OUTPUT on 0.15 % of samples, max |d| 62 -- while my provenance stamp,
# taken once at start, still claimed the old md5.  Re-stat per row and ABORT on
# any change: a table whose rows came from two binaries is not a table.
BIN_LOCK="$ENCMD5/$DECMD5"
check_bin(){
  local now="$(md5sum $G/omc_enc | cut -c1-12)/$(md5sum $G/omc_dec | cut -c1-12)"
  if [ "$now" != "$BIN_LOCK" ]; then
    echo "*** ABORT: shared tree binaries changed mid-run: $BIN_LOCK -> $now" >>$LOG
    echo "*** rows already written used $BIN_LOCK; stopping rather than mixing." >>$LOG
    exit 9
  fi; }

# cut frames [f0,f0+n) out of an arm-shaped file
cut_win(){ src=$1 dst=$2 W=$3 H=$4 fmt=$5 f0=$6 n=$7
  local cw=$W; [ "$fmt" = 422 ] && cw=$((W/2))
  local fb=$(( (W*H + 2*cw*H) * 2 ))
  dd if="$src" of="$dst" bs=$fb skip=$f0 count=$n status=none; }

omc_encode(){ arm=$1 W=$2 H=$3 fmt=$4 dep=$5 bpp=$6 out=$7
  "$G/omc_enc" -i "$arm" -o "$out" -w $W -h $H --fmt $fmt --depth $dep --bpp $bpp -n 24 \
      >/dev/null 2>"$out.err"; return $?; }

row(){ arm=$1 clip=$2 W=$3 H=$4 fmt=$5 dep=$6 obpp=$7 xbpp=$8
  check_bin
  local base=$(basename $arm .yuv)
  local armmd5=$(md5sum "$arm" | cut -c1-12)
  local st=$TMPDIR/m3_$$.omc od=$TMPDIR/m3o_$$.yuv xd=$TMPDIR/m3x_$$.yuv
  # ---- OMC (cache the stream+decode per arm+rate)
  local ok=$O/cache_${base}_o${obpp}.yuv
  if [ ! -s "$ok" ]; then
    omc_encode "$arm" $W $H $fmt $dep $obpp $st
    if [ $? -ne 0 ] || [ ! -s $st ]; then
      echo "ROW $base omc@$obpp xs@$xbpp : OMC-ENCFAIL $(tail -1 $st.err 2>/dev/null|cut -c1-70)" >>$LOG
      rm -f $st $st.err; return; fi
    "$G/omc_dec" -i $st -o $ok >/dev/null 2>&1 || { echo "ROW $base omc@$obpp : OMC-DECFAIL" >>$LOG; rm -f $st $st.err $ok; return; }
    rm -f $st $st.err
  fi
  # ---- XS (cache per arm+rate)
  local xk=$O/cache_${base}_x${xbpp}.yuv
  if [ ! -s "$xk" ]; then
    bash $XSRUN "$arm" $xk $W $H $fmt $dep 24 $xbpp >$TMPDIR/xs_$$.log 2>&1
    if [ $? -ne 0 ] || [ ! -s "$xk" ]; then
      echo "ROW $base omc@$obpp xs@$xbpp : XS-N/A $(grep -iE 'error|not supported|invalid' $TMPDIR/xs_$$.log | head -1 | cut -c1-70)" >>$LOG
      rm -f $xk $TMPDIR/xs_$$.log; return; fi
    rm -f $TMPDIR/xs_$$.log
  fi
  # ---- two windows
  for f0 in 8 16; do
    local tagr="f${f0}-f$((f0+7))"
    local ws=$W_DIR/${base}_src_$f0.yuv
    local wo=$W_DIR/${base}_o${obpp}_$f0.yuv
    local wx=$W_DIR/${base}_x${xbpp}_$f0.yuv
    [ -s "$ws" ] || cut_win "$arm" "$ws" $W $H $fmt $f0 8
    [ -s "$wo" ] || cut_win "$ok"  "$wo" $W $H $fmt $f0 8
    [ -s "$wx" ] || cut_win "$xk"  "$wx" $W $H $fmt $f0 8
    python3 $P/Agents/Agent5/harness/lat_m3_row.py "$ws" "$wo" "$wx" $W $H $fmt $dep \
        "$base" "$obpp" "$xbpp" "$tagr" "$armmd5" "$ENCMD5" "$DECMD5" >>$LOG 2>>$O/row_err.log
  done; }

# ---------------------------------------------------------------- the ladder
CLIPS="highwaydrive highwayview officewalk spotrobot trafficlights volleyballgame winterdrive floorballtrain floorballgame"
: > $LOG
echo "# M3 ladder — Task G tree minor 16, enc=$ENCMD5 dec=$DECMD5, XS at best (-q 1 --rc 2 --slice-height 32)" >>$LOG
echo "# arms: .work/arms/long, 24 frames from source frame 0; runs f8-f15 and f16-f23" >>$LOG

case "${PHASE:-A}" in
A)  echo "== section 1: 1080p 4:2:2 10-bit ==" >>$LOG
    for c in $CLIPS; do a=$A/${c}L_1920x1080_422_10.yuv; [ -f "$a" ] || { echo "MISSING $c 422" >>$LOG; continue; }
      row "$a" $c 1920 1080 422 10 0.5 1.0
      row "$a" $c 1920 1080 422 10 1.0 2.0
      row "$a" $c 1920 1080 422 10 0.5 0.5
      rm -f $O/cache_${c}L_1920x1080_422_10_*.yuv
    done ;;
B)  echo "== section 2: 1080p 4:4:4 12-bit ==" >>$LOG
    for c in $CLIPS; do a=$A/${c}L_1920x1080_444_12.yuv; [ -f "$a" ] || { echo "MISSING $c 444" >>$LOG; continue; }
      row "$a" $c 1920 1080 444 12 0.5 1.0
      row "$a" $c 1920 1080 444 12 1.0 2.0
      rm -f $O/cache_${c}L_1920x1080_444_12_*.yuv
    done ;;
C)  echo "== section 3: 4K 4:4:4 12-bit ==" >>$LOG
    for c in $CLIPS; do a=$A/${c}L_3840x2160_444_12.yuv; [ -f "$a" ] || { echo "MISSING $c 4K" >>$LOG; continue; }
      row "$a" $c 3840 2160 444 12 1.0 2.0
      rm -f $O/cache_${c}L_3840x2160_444_12_*.yuv
    done ;;
esac
echo "M3-PHASE-${PHASE:-A}-DONE $(date)" >>$LOG

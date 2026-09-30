#!/bin/bash
# [A5-GATE7] Gate suite for tree_all = base + the MEMO 002 code fixes + the 9-item MEMO 004 doc pass ([A5-LAZYCOST] +
# [A5-LATTMEMO]) against the PRISTINE v54tree_int binaries -- not against my own
# instrumented build.  Same discipline as gates 1-4: exit codes and file sizes
# checked before any cmp; a failed run never becomes a number.
set -u
ROOT=/home/user/fromscratch/OMC_CLOUD/Project
P=$ROOT/.work/v54tree_int          # pristine base, its own binaries
T=$ROOT/Agents/Agent5/tree_all    # base + memo002 code fixes + the 9-item doc pass
A=$ROOT/.work/arms; A1=$ROOT/Agents/Agent1/arms
export TMPDIR=$ROOT/.work/scratch/tmp; mkdir -p "$TMPDIR"
G=$ROOT/Agents/Agent5/out/gates_all.log; : > "$G"
# per-run private temp dir: fixed filenames let a concurrent run corrupt the
# comparison silently, in EITHER direction.  Cost me a spurious DIFFERS today.
RUN=$(mktemp -d "$TMPDIR/g7.XXXXXX"); trap "rm -rf $RUN" EXIT

ident(){ c=$1 d=$2 W=$3 H=$4 f=$5 p=$6 b=$7 n=${8:-12}
  [ -f "$d/$c.yuv" ] || { echo "G7 MISSING $c" >>"$G"; return; }
  "$P/omc_enc" -i "$d/$c.yuv" -o "$RUN/b6p.omc" -w $W -h $H --fmt $f --depth $p --bpp $b -n $n >/dev/null 2>&1 || { echo "G7 ENCFAIL-pristine $c@$b" >>"$G"; return; }
  "$T/omc_enc" -i "$d/$c.yuv" -o "$RUN/b6n.omc" -w $W -h $H --fmt $f --depth $p --bpp $b -n $n >/dev/null 2>&1 || { echo "G7 ENCFAIL-all $c@$b" >>"$G"; return; }
  [ -s "$RUN/b6p.omc" ] && [ -s "$RUN/b6n.omc" ] || { echo "G7 EMPTY $c@$b" >>"$G"; return; }
  "$P/omc_dec" -i "$RUN/b6p.omc" -o "$RUN/b6p.yuv" >/dev/null 2>&1 || { echo "G7 DECFAIL-pristine $c@$b" >>"$G"; return; }
  "$T/omc_dec" -i "$RUN/b6n.omc" -o "$RUN/b6n.yuv" >/dev/null 2>&1 || { echo "G7 DECFAIL-all $c@$b" >>"$G"; return; }
  [ -s "$RUN/b6p.yuv" ] && [ -s "$RUN/b6n.yuv" ] || { echo "G7 EMPTYDEC $c@$b" >>"$G"; return; }
  if cmp -s "$RUN/b6p.omc" "$RUN/b6n.omc" && cmp -s "$RUN/b6p.yuv" "$RUN/b6n.yuv"; then
    echo "G7 IDENTICAL $c@$b ($(stat -c%s "$RUN/b6p.omc") stream, $(stat -c%s "$RUN/b6p.yuv") decode)" >>"$G"
  else echo "G7 DIFFERS $c@$b" >>"$G"; fi
  rm -f "$RUN"/b6*.omc "$RUN"/b6*.yuv; }

ident dng_1280x720_422_10   $A 1280  720 422 10 0.5
ident dng_1280x720_422_10   $A 1280  720 422 10 1.0
ident dng_1920x1080_422_10  $A 1920 1080 422 10 0.4
ident dng_1920x1080_422_10  $A 1920 1080 422 10 0.5
ident dng_1920x1080_422_10  $A 1920 1080 422 10 2.0
ident dng_1920x1080_422_10  $A 1920 1080 422 10 4.0
ident cityalley_1920x1080_422_10  $A 1920 1080 422 10 0.5
ident bosphorus_1920x1080_422_10  $A 1920 1080 422 10 0.5
ident readysetgo_1920x1080_422_10 $A 1920 1080 422 10 0.5
ident cf_gfx_448x256_422_10 $A  448  256 422 10 0.5
ident cf_gfx512_512x256_422_10 $A 512 256 422 10 0.5
ident dng_1920x1080_422_8   $A 1920 1080 422  8 0.5
ident dng_1920x1080_422_12  $A 1920 1080 422 12 1.0
ident dng_1920x1080_444_10  $A 1920 1080 444 10 0.5
ident dng_1920x1080_444_12  $A 1920 1080 444 12 0.5
ident dng_3840x2160_422_10  $A 3840 2160 422 10 0.5 6
ident dng_7680x4320_422_10  $A 7680 4320 422 10 0.5 3
ident soccer_1920x1080_422_10 $A 1920 1080 422 10 0.5
ident runA_1920x1080_422_10   $A 1920 1080 422 10 1.0
ident spotrobot_1920x1080_422_10 $A1 1920 1080 422 10 0.4
ident officewal_1920x1080_422_10 $A1 1920 1080 422 10 0.5
ident winter_1920x1080_422_10    $A1 1920 1080 422 10 0.5
ident highway_1920x1080_444_12   $A1 1920 1080 444 12 0.5
ident volley_1920x1080_444_10    $A1 1920 1080 444 10 0.5
ident runner_1920x1080_422_10    $A1 1920 1080 422 10 0.5
ident trafficli_1920x1080_422_10 $A1 1920 1080 422 10 0.5
echo "G7-IDENT-DONE" >>"$G"

# chains on the both-fixes tree
chain(){ MODE=$1; SRC=$2; W=$3; H=$4; F=$5; PP=$6; B=$7; N=$8; NG=$9
  tmp=$(mktemp -d "$TMPDIR/a6ch.XXXXXX"); cur=$SRC
  SH=$([ $H -le 720 ] && echo 8 || echo 16); CH=$(( (H+SH-1)/SH*SH )); ok=PASS; why=""
  for g in $(seq 1 $NG); do
    if [ $MODE = cdr ] && [ $g -gt 1 ]; then
      "$T/omc_enc" -i $cur -o $tmp/s$g.omc -w $W -h $CH --fmt $F --depth $PP --bpp $B -n $N --display-w $W --display-h $H --cdr-in >/dev/null 2>&1
    else
      "$T/omc_enc" -i $cur -o $tmp/s$g.omc -w $W -h $H --fmt $F --depth $PP --bpp $B -n $N >/dev/null 2>&1
    fi
    rc=$?   # [V536] Agent 5 E26: an rc=2 encode ("EXACTNESS NOT DELIVERED") still writes a playable stream; check the status, not only the file
    [ $rc -eq 0 ] && [ -s $tmp/s$g.omc ] || { ok=FAIL; why="enc-gen$g rc=$rc"; break; }
    if [ $MODE = cdr ]; then "$T/omc_dec" -i $tmp/s$g.omc --cdr -o $tmp/d$g.yuv >/dev/null 2>&1
    else "$T/omc_dec" -i $tmp/s$g.omc -o $tmp/d$g.yuv >/dev/null 2>&1; fi
    rc=$?; [ $rc -eq 0 ] && [ -s $tmp/d$g.yuv ] || { ok=FAIL; why="dec-gen$g rc=$rc"; break; }
    if [ $g -ge 2 ]; then cmp -s $tmp/d$g.yuv $tmp/d$((g-1)).yuv || { ok=FAIL; why="pixels-gen$g"; break; }; fi
    # [V536] Agent 5 E27: compare the STREAM too from gen 3 on -- a committed excursion is clipped out of a decode, never out of a stream
    if [ $g -ge 3 ]; then cmp -s $tmp/s$g.omc $tmp/s$((g-1)).omc || { ok=FAIL; why="stream-gen$g"; break; }; fi
    cur=$tmp/d$g.yuv
  done
  echo "G7 CHAIN-$MODE $(basename $SRC .yuv)@$B gens=$NG : $ok $why" >>"$G"; rm -rf $tmp; }
chain cdr $A/dng_1920x1080_422_10.yuv 1920 1080 422 10 1.0 6 8
chain cdr $A/dng_1920x1080_444_10.yuv 1920 1080 444 10 1.0 6 8
chain cdr $A/dng_1920x1080_422_8.yuv  1920 1080 422  8 2.0 6 8
chain cdr $A/cf_gfx_448x256_422_10.yuv 448 256 422 10 0.5 6 8
chain cdr $A/dng_1280x720_422_10.yuv  1280  720 422 10 1.0 6 8
chain cdr $A1/spotrobot_1920x1080_422_10.yuv 1920 1080 422 10 0.4 6 8
chain baseband $A/dng_1920x1080_422_10.yuv 1920 1080 422 10 1.0 6 8
chain baseband $A/dng_1920x1080_444_10.yuv 1920 1080 444 10 1.0 6 8
chain baseband $A/cf_gfx_448x256_422_10.yuv 448 256 422 10 0.5 6 8
chain baseband $A1/officewal_1920x1080_422_10.yuv 1920 1080 422 10 0.5 6 8
echo "G7-CHAIN-DONE" >>"$G"
echo "G7-DONE $(date)" >>"$G"

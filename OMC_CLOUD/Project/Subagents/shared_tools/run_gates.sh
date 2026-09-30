#!/bin/bash
# v5.3.6 release gate battery -- runs on the tree's built binaries; the tree must NOT be rebuilt while this runs
T=/home/user/fromscratch/OMC_CLOUD/Project/.work/v536; L=/home/user/fromscratch/OMC_CLOUD/Project/.work/logs/fable_2026-09-08/v536_gates; A=/home/user/fromscratch/OMC_CLOUD/Project/.work/arms; S=$L/tmp; mkdir -p $S; cd $T
echo "BATTERY START $(date -u +%FT%TZ)"; md5sum omc_enc omc_dec | tee $L/binaries.md5
echo "== build: warnings"; make -B all > $L/build.log 2>&1; echo "warnings=$(grep -c 'warning:' $L/build.log) errors=$(grep -c 'error:' $L/build.log)"; md5sum omc_enc omc_dec | diff - $L/binaries.md5 > /dev/null && echo "rebuild reproduces the same binaries: yes" || echo "rebuild binaries differ (expected if -g paths moved; streams are compared below)"
echo "== suites"; for t in test_unit test_uc test_cc test_cap; do ./$t > $L/$t.log 2>&1; echo "$t rc=$? ok=$(grep -c '^ok' $L/$t.log) fail=$(grep -c '^FAIL' $L/$t.log)"; done
./test_xsl > $L/test_xsl.log 2>&1; echo "test_xsl rc=$? ok=$(grep -c '^ok' $L/test_xsl.log) fail=$(grep -c '^FAIL' $L/test_xsl.log) $(grep -m1 CUT24 $L/test_xsl.log | cut -c1-40)"
echo "== restore / refcheck"; sh tests/restore_check.sh > $L/restore.log 2>&1; echo "restore rc=$? $(head -1 $L/restore.log)"; sh tests/refcheck.sh > $L/refcheck.log 2>&1; echo "refcheck rc=$? $(tail -1 $L/refcheck.log | cut -c1-80)"
echo "== fuzz"; TMPDIR=$S sh tests/fuzz_check.sh 400 > $L/fuzz.log 2>&1; echo "fuzz rc=$? $(grep -m1 'fuzz build' $L/fuzz.log | cut -c1-60) | $(grep 'CRCFUZZ done\|unstructured fuzz\|^ok:\|FAIL' $L/fuzz.log | tr '\n' ' ' | cut -c1-200)"
echo "== rt=0 / exact CBR / version gate / freeze control"
for cell in "dng_1920x1080_422_10 1920 1080 422 10 0.5" "dng_1920x1080_444_12 1920 1080 444 12 1.0" "dng_1920x1080_422_8 1920 1080 422 8 1.0" "cf_gfx_448x256_422_10 448 256 422 10 0.5" "dng_1280x720_422_10 1280 720 422 10 2.0"; do set -- $cell
  ./omc_enc -i $A/$1.yuv -o $S/c.omc -w $2 -h $3 --fmt $4 --depth $5 --bpp $6 -n 3 --recon $S/rec.yuv > $S/e.log 2>&1; rc=$?
  ./omc_dec -i $S/c.omc --cdr -o $S/cdr.yuv > /dev/null 2>&1; cmp -s $S/rec.yuv $S/cdr.yuv && rt=RT0 || rt=RT-MISMATCH
  sz=$(stat -c%s $S/c.omc); echo "$1 @$6: $rt enc-rc=$rc size=$sz frames=3 $(python3 -c "s=$sz-32; print('CBR-EXACT' if s%3==0 and (s//3)%8==0 else 'CBR-CHECK')") $(grep -m1 'baseband-safe' $S/e.log)"
done
echo "== v5.3.5 compatibility (minor 16 unchanged): same-input identity and cross-decoding"
for cell in "dng_1920x1080_422_10 1920 1080 422 10 0.5" "dng_1920x1080_444_12 1920 1080 444 12 1.0" "dng_1920x1080_422_8 1920 1080 422 8 1.0" "cf_gfx_448x256_422_10 448 256 422 10 0.5"; do set -- $cell
  ./omc_enc -i $A/$1.yuv -o $S/n.omc -w $2 -h $3 --fmt $4 --depth $5 --bpp $6 -n 6 >/dev/null 2>&1; ../v535/omc_enc -i $A/$1.yuv -o $S/o.omc -w $2 -h $3 --fmt $4 --depth $5 --bpp $6 -n 6 >/dev/null 2>&1
  ../v535/omc_dec -i $S/n.omc -o $S/xd.yuv >/dev/null 2>&1; ./omc_dec -i $S/n.omc -o $S/nd.yuv >/dev/null 2>&1
  echo "$1 @$6: v5.3.6 stream vs v5.3.5 stream $(cmp -s $S/n.omc $S/o.omc && echo IDENTICAL || echo DIFFERS); v5.3.5 decoder on the v5.3.6 stream $(cmp -s $S/xd.yuv $S/nd.yuv && echo IDENTICAL-DECODE || echo DIFFERS)"; done
./omc_dec -i $S/c.omc -o $S/d1.yuv > /dev/null 2>&1; OMC_VEXT=-2 OMC_VEXT_LVL=2 ./omc_dec -i $S/c.omc -o $S/d2.yuv 2> $S/fz.log; cmp -s $S/d1.yuv $S/d2.yuv && echo "freeze control: decoder env OMC_VEXT=-2 LVL=2 -> IDENTICAL decode; warnings: $(grep -c NORMATIVE $S/fz.log)" || echo "freeze control: DECODE DIFFERS (C8 HOLE)"
OMC_VEXT=-2 OMC_VEXT_LVL=2 ./omc_enc -i $A/dng_1280x720_422_10.yuv -o $S/c0.omc -w 1280 -h 720 --fmt 422 --depth 10 --bpp 2.0 -n 3 > /dev/null 2>&1; cmp -s $S/c0.omc $S/c.omc && echo "encoder lever OMC_VEXT=-2: NO EFFECT (?)" || echo "encoder lever OMC_VEXT=-2 changes the stream (live A/B lever, decoder pinned): yes"
echo "== CDR chains, 8 generations"
chain() { name=$1; W=$2; H=$3; F=$4; PP=$5; B=$6; NF=$7; src=$A/$name.yuv; CH=$(( (H+15)/16*16 )); tmp=$(mktemp -d -p $S); ok=PASS; why=""; moved=""; rcs=""
  for g in 1 2 3 4 5 6 7 8; do
    if [ $g -gt 1 ]; then ./omc_enc -i $tmp/d$((g-1)).yuv -o $tmp/s$g.omc -w $W -h $CH --fmt $F --depth $PP --bpp $B -n $NF --display-w $W --display-h $H --cdr-in > $tmp/e$g.log 2>&1; rc=$?
    else ./omc_enc -i $src -o $tmp/s$g.omc -w $W -h $H --fmt $F --depth $PP --bpp $B -n $NF > $tmp/e$g.log 2>&1; rc=$?; fi
    rcs="$rcs $rc"; [ -s $tmp/s$g.omc ] || { ok=FAIL; why="enc-gen$g rc=$rc: $(grep -m1 -i 'exactness\|error' $tmp/e$g.log | cut -c1-90)"; break; }
    ./omc_dec -i $tmp/s$g.omc --cdr -o $tmp/d$g.yuv > /dev/null 2>&1; [ -s $tmp/d$g.yuv ] || { ok=FAIL; why="dec-gen$g"; break; }
    if [ $g -ge 2 ]; then m=$(cmp -l $tmp/d$g.yuv $tmp/d$((g-1)).yuv 2>/dev/null | wc -l); sm=$(cmp -s $tmp/s$g.omc $tmp/s$((g-1)).omc && echo = || echo x); moved="$moved $m$sm"; fi
  done; [ "$ok" = PASS ] && [ "${moved##* }" != "0=" ] && ok=NOTFIXED
  echo "CDR $name @$B ${NF}f: $ok $why | rc:$rcs | moved gen2..8:$moved"; rm -rf $tmp; }
chain dng_1920x1080_422_10 1920 1080 422 10 0.5 6; chain dng_1920x1080_444_12 1920 1080 444 12 0.5 6; chain dng_1920x1080_422_8 1920 1080 422 8 1.0 6; chain cf_gfx_448x256_422_10 448 256 422 10 0.5 6
chain soccer2_1920x1080_422_10 1920 1080 422 10 0.5 6; chain long/highwaydriveL_1920x1080_422_10 1920 1080 422 10 0.5 6; chain long/highwaydriveL_1920x1080_444_12 1920 1080 444 12 0.5 6; chain dng_1280x720_422_10 1280 720 422 10 0.5 6
chain long/highwayviewL_1920x1080_444_12 1920 1080 444 12 1.0 12; chain long/officewalkL_1920x1080_422_10 1920 1080 422 10 0.5 12
echo "== baseband chain (display-clipped decode re-encoded), 4 generations, 2 cells"
for cell in "dng_1920x1080_422_10 1920 1080 422 10 0.5" "cf_gfx_448x256_422_10 448 256 422 10 0.5"; do set -- $cell; tmp=$(mktemp -d -p $S); ./omc_enc -i $A/$1.yuv -o $tmp/s1.omc -w $2 -h $3 --fmt $4 --depth $5 --bpp $6 -n 6 >/dev/null 2>&1; ./omc_dec -i $tmp/s1.omc -o $tmp/d1.yuv >/dev/null 2>&1; moved=""
  for g in 2 3 4; do ./omc_enc -i $tmp/d$((g-1)).yuv -o $tmp/s$g.omc -w $2 -h $3 --fmt $4 --depth $5 --bpp $6 -n 6 >/dev/null 2>&1; ./omc_dec -i $tmp/s$g.omc -o $tmp/d$g.yuv >/dev/null 2>&1; moved="$moved $(cmp -l $tmp/d$g.yuv $tmp/d$((g-1)).yuv 2>/dev/null | wc -l)$(cmp -s $tmp/s$g.omc $tmp/s$((g-1)).omc && echo = || echo x)"; done; echo "BASEBAND $1 @$6: moved gen2..4:$moved"; rm -rf $tmp; done
echo "== seam instruments on the shipped default (fill off), frame 8"; N3=/home/user/fromscratch/OMC_CLOUD/Project/Agents/Agent3/notes
for cell in "dng_1920x1080_422_10 1920 1080 422 10 0.5" "dng_1920x1080_444_12 1920 1080 444 12 1.0"; do set -- $cell; ./omc_enc -i $A/$1.yuv -o $S/s.omc -w $2 -h $3 --fmt $4 --depth $5 --bpp $6 -n 12 >/dev/null 2>&1; ./omc_dec -i $S/s.omc -o $S/s.yuv >/dev/null 2>&1; echo "$1 @$6: $(python3 $N3/replprofile_a3.py $A/$1.yuv $S/s.yuv $2 $3 $4 $5 8 16 | grep excess)"; done
echo "== timing (loaded machine, informational)"; /usr/bin/time -f "enc 1080p 4:2:2 10 @0.5 8f: %e s wall" ./omc_enc -i $A/dng_1920x1080_422_10.yuv -o $S/t.omc -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 0.5 -n 8 2>&1 >/dev/null | tail -1; /usr/bin/time -f "dec: %e s wall" ./omc_dec -i $S/t.omc -o $S/t.yuv 2>&1 >/dev/null | tail -1
rm -rf $S; echo "BATTERY DONE $(date -u +%FT%TZ)"

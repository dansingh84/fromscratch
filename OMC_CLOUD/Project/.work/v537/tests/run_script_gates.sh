#!/bin/bash
# Script-level gates that complement test_xsl (which is compiled C).  Run
# from the tree root after `make`.  Exit non-zero on any failure.
cd "$(dirname "$0")/.."
W=/home/user/fromscratch/OMC_CLOUD/Project/.work
rc=0
bash tests/restore_check.sh 2>&1 | grep -E "RESTORE ok|FAIL" | head -1 | grep -q "RESTORE ok" || { echo "FAIL: G-T5-RESTORE"; rc=1; }
for arm in "dng_1920x1080_422_10 1920 1080 422 10 0.5" "cf_gfx_448x256_422_10 448 256 422 10 0.5" "dng_1920x1080_444_10 1920 1080 444 10 0.5"; do
  set -- $arm
  out=$(bash tests/spend_check.sh ./omc_enc ./omc_dec $W/arms/$1.yuv $2 $3 $4 $5 $6 12); echo "$out ($1@$6)"
  echo "$out" | grep -q "^ok:" || rc=1
done
[ $rc -eq 0 ] && echo "script gates: all ok" || echo "script gates: FAILURES"
exit $rc

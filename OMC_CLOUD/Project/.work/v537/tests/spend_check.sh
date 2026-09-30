#!/bin/bash
# G-T5-SPEND (sect.51.29 item 3): the generation lock's spend invariant.
# At generation 2, every LOCKED slice must emit no more bytes than the same
# slice did at generation 1 (docs/TEMPORAL_T5.md section 8 step 4).  This
# is the invariant behind three historical breaks (5.5.4, 5.5.6, B5.5): a
# locked slice growing by one byte drains the causal bank and starves a
# later budget-edge slice of its own plan.  About 1 in 100 slices sits
# exactly at its hard budget, so the class is common, not a freak.
#
# Runs a 2-generation CDR chain (clamp mode, the most exposed configuration)
# on the arm given, dumps per-slice sizes with OMC_DEBUG_SIZES, and fails on
# any locked generation-2 slice whose bytes exceed generation 1's.
# usage: spend_check.sh ENC DEC ARM W H FMT DEPTH BPP NF
E=$1; D=$2; A=$3; W=$4; H=$5; FMT=$6; DP=$7; BPP=$8; NF=${9:-12}
T=$(mktemp -d); SH=$([ $H -le 720 ] && echo 8 || echo 16); CH=$(( (H+SH-1)/SH*SH ))
OMC_DEBUG_SIZES=1 $E -i $A -o $T/s1.omc -w $W -h $H --fmt $FMT --depth $DP --bpp $BPP -n $NF --no-gamut-strict 2>$T/g1.log >/dev/null || { echo "G-T5-SPEND ERROR: gen1 encode failed"; rm -rf $T; exit 2; }
$D -i $T/s1.omc --cdr -o $T/d1.yuv >/dev/null 2>&1
OMC_DEBUG_SIZES=1 $E -i $T/d1.yuv -o $T/s2.omc -w $W -h $CH --fmt $FMT --depth $DP --bpp $BPP -n $NF --display-w $W --display-h $H --cdr-in --no-gamut-strict 2>$T/g2.log >/dev/null || { echo "G-T5-SPEND ERROR: gen2 encode failed"; rm -rf $T; exit 2; }
python3 - "$T/g1.log" "$T/g2.log" << 'PYEOF'
import re, sys
def last(f):
    d={}
    for ln in open(f):
        m=re.match(r"SZ f(\d+) s(\d+) bytes=(\d+) locked=(\d)",ln)
        if m: d[(int(m[1]),int(m[2]))]=(int(m[3]),int(m[4]))
    return d
g1=last(sys.argv[1]); g2=last(sys.argv[2])
grew=[(k,g1[k][0],g2[k][0]) for k in g2 if k in g1 and g2[k][1]==1 and g2[k][0]>g1[k][0]]
unlocked=[k for k in g2 if g2[k][1]==0]
nl=sum(1 for k in g2 if g2[k][1]==1)
if grew:
    print(f"FAIL: G-T5-SPEND {len(grew)} locked generation-2 slices spend MORE than generation 1: {[(f'f{k[0]}s{k[1]}',a,b) for k,a,b in grew[:8]]}")
    sys.exit(1)
if unlocked:
    print(f"FAIL: G-T5-SPEND {len(unlocked)} generation-2 slices did not lock: {[f'f{k[0]}s{k[1]}' for k in unlocked[:8]]}")
    sys.exit(1)
print(f"ok: G-T5-SPEND every locked generation-2 slice ({nl}) spends no more than generation 1's identical slice")
PYEOF
rc=$?; rm -rf $T; exit $rc

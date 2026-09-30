#!/bin/bash
# genchain.sh TREE ARM W H FMT DEPTH BPP NFRAMES GENS MODE
#   MODE = baseband   : each hop hands over the DECODED picture (an SDI hop);
#          cdr        : each hop hands over the CDR (coded-domain) picture and
#                       the re-encode declares --cdr-in.
# A4 requires the chain to be byte-identical from generation 2 onward: stream
# and picture both.  Prints PASS/FAIL and the first generation that differs.
W_=$(cd "$(dirname "$0")/.." && pwd)
T=$1; A=$2; WD=$3; HT=$4; FMT=$5; DP=$6; BPP=$7; NF=$8; G=${9:-4}; M=${10:-baseband}
case "$T" in v51) TD=$W_/v51/omc_v5.1.1 ;; v510) TD=$W_/v510/omc_v5.1 ;; *) TD=$W_/$T/omc_v5 ;; esac
E=$TD/omc_enc; D=$TD/omc_dec
# GUARD (2026-08-26).  Twice in one session this harness reported a wall of
# FAILs that were not the codec: once because the tree had been renamed under
# it, once because `make clean` had removed the binaries before a zip build.  A
# missing binary must stop the run loudly, never be reported as a failed
# generation chain.
[ -x "$E" ] || { echo "HARNESS ERROR: encoder not built or not found: $E" >&2; exit 99; }
[ -x "$D" ] || { echo "HARNESS ERROR: decoder not built or not found: $D" >&2; exit 99; }
tmp=$(mktemp -d ${SCR:-/tmp}/gc.XXXXXX)
SHB=$( [ $HT -le 720 ] && echo 8 || echo 16 ); CH=$(( (HT + SHB - 1) / SHB * SHB ))
cur=$A; extra=""
for g in $(seq 1 $G); do
  [ "$M" = cdr ] && [ $g -gt 1 ] && extra="--cdr-in"
  if [ "$M" = cdr ]; then
    if [ $g -gt 1 ]; then
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $CH --fmt $FMT --depth $DP --bpp $BPP -n $NF \
         --display-w $WD --display-h $HT --cdr-in >/dev/null 2>&1 || true
    else
      $E -i $cur -o $tmp/s$g.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n $NF >/dev/null 2>&1 || true
    fi
    $D -i $tmp/s$g.omc -o $tmp/p$g.yuv --cdr >/dev/null 2>&1
  else
    $E -i $cur -o $tmp/s$g.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n $NF >/dev/null 2>&1 || true
    $D -i $tmp/s$g.omc -o $tmp/p$g.yuv >/dev/null 2>&1
  fi
  cur=$tmp/p$g.yuv
done
bad=""
for g in $(seq 3 $G); do
  cmp -s $tmp/s$((g-1)).omc $tmp/s$g.omc || bad="$bad stream@g$g"
  cmp -s $tmp/p$((g-1)).yuv $tmp/p$g.yuv || bad="$bad pic@g$g"
done
printf "%-4s %-11s %-4s %-4s %-7s %-9s %s\n" "$T" "${WD}x${HT}" "$FMT" "${DP}b" "${BPP}bpp" "$M" \
  "$( [ -z "$bad" ] && echo "PASS (gen2..gen$G byte-identical)" || echo "FAIL:$bad" )"
rm -rf $tmp

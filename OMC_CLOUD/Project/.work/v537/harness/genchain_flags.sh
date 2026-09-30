#!/bin/bash
# genchain_flags.sh TREE ARM W H FMT DEPTH BPP NFRAMES GENS MODE [ENCODER FLAGS...]
#
# The same A4 generation chain as h/genchain.sh, but every generation is encoded
# with the SAME extra encoder flags.  Written 2026-08-26 to answer one question
# the owner asked directly: with grain fill re-enabled, does byte-exactness
# survive?  h/genchain.sh cannot answer it because it takes no encoder flags,
# and running the chain with fill on generation 1 only would answer a different
# and meaningless question.
#
# A4 requires generations 2..N to be byte-identical, stream AND picture.
set -u
W_=$(cd "$(dirname "$0")/.." && pwd)
T=$1; A=$2; WD=$3; HT=$4; FMT=$5; DP=$6; BPP=$7; NF=$8; G=${9:-4}; M=${10:-baseband}; shift 10
case "$T" in v51) TD=$W_/v51/omc_v5.1.1 ;; v510) TD=$W_/v510/omc_v5.1 ;; *) TD=$W_/$T/omc_v5 ;; esac
E=$TD/omc_enc; D=$TD/omc_dec
[ -x "$E" ] || { echo "HARNESS ERROR: encoder not built: $E" >&2; exit 99; }
[ -x "$D" ] || { echo "HARNESS ERROR: decoder not built: $D" >&2; exit 99; }
tmp=$(mktemp -d ${SCR:-/tmp}/gcf.XXXXXX)
SHB=$( [ $HT -le 720 ] && echo 8 || echo 16 ); CH=$(( (HT + SHB - 1) / SHB * SHB ))
cur=$A
for g in $(seq 1 $G); do
  if [ "$M" = cdr ] && [ $g -gt 1 ]; then
    $E -i $cur -o $tmp/s$g.omc -w $WD -h $CH --fmt $FMT --depth $DP --bpp $BPP -n $NF \
       --display-w $WD --display-h $HT --cdr-in "$@" >/dev/null 2>&1 || true
    $D -i $tmp/s$g.omc -o $tmp/p$g.yuv --cdr >/dev/null 2>&1
  elif [ "$M" = cdr ]; then
    $E -i $cur -o $tmp/s$g.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n $NF "$@" >/dev/null 2>&1 || true
    $D -i $tmp/s$g.omc -o $tmp/p$g.yuv --cdr >/dev/null 2>&1
  else
    $E -i $cur -o $tmp/s$g.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n $NF "$@" >/dev/null 2>&1 || true
    $D -i $tmp/s$g.omc -o $tmp/p$g.yuv >/dev/null 2>&1
  fi
  cur=$tmp/p$g.yuv
done
bad=""
for g in $(seq 3 $G); do
  cmp -s $tmp/s$((g-1)).omc $tmp/s$g.omc || bad="$bad stream@g$g"
  cmp -s $tmp/p$((g-1)).yuv $tmp/p$g.yuv || bad="$bad pic@g$g"
done
if [ -z "$bad" ]; then
  printf "%-4s %-11s %-4s %-4s %-7s %-9s %-22s PASS (gen2..gen%s byte-identical)\n" \
    "$T" "${WD}x${HT}" "$FMT" "${DP}b" "${BPP}bpp" "$M" "$*" "$G"
else
  printf "%-4s %-11s %-4s %-4s %-7s %-9s %-22s FAIL:%s\n" \
    "$T" "${WD}x${HT}" "$FMT" "${DP}b" "${BPP}bpp" "$M" "$*" "$bad"
fi
rm -rf $tmp

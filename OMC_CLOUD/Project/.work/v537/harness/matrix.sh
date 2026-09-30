#!/bin/bash
# matrix.sh TREE ARM W H FMT DEPTH BPP NFRAMES [SLICEH|-] [EXTRA...]
# One matrix cell: encode, decode, C4 rt=0, gamut oob, VMAF-NEG (10-bit only),
# per-plane PSNR (C5) and the sect.51 BLOTCH level metric.
W_=$(cd "$(dirname "$0")/.." && pwd)
T=$1; A=$2; WD=$3; HT=$4; FMT=$5; DP=$6; BPP=$7; NF=$8; SH=$9; shift 9
case "$T" in v51) TD=$W_/v51/omc_v5.1.1 ;; *) TD=$W_/$T/omc_v5 ;; esac
E=$TD/omc_enc; D=$TD/omc_dec
# GUARD (2026-08-26).  Twice in one session this harness reported a wall of
# FAILs that were not the codec: once because the tree had been renamed under
# it, once because `make clean` had removed the binaries before a zip build.  A
# missing binary must stop the run loudly, never be reported as a failed
# generation chain.
[ -x "$E" ] || { echo "HARNESS ERROR: encoder not built or not found: $E" >&2; exit 99; }
[ -x "$D" ] || { echo "HARNESS ERROR: decoder not built or not found: $D" >&2; exit 99; }
tmp=$(mktemp -d ${SCR:-/tmp}/mx.XXXXXX)
sh_arg=""; shb=""
if [ -n "$SH" ] && [ "$SH" != "-" ]; then sh_arg="--slice-h $SH"; shb=$SH; fi
g=$($E -i $A -o $tmp/s.omc -w $WD -h $HT --fmt $FMT --depth $DP --bpp $BPP -n $NF \
      --recon $tmp/rec.yuv $sh_arg "$@" 2>&1); rc=$?
oob=$(echo "$g" | grep -oP 'gamut: \K[0-9]+'); [ -z "$oob" ] && oob="?"
[ -z "$shb" ] && shb=$(echo "$g" | grep -oP 'slice-h \K[0-9]+')
[ -z "$shb" ] && shb=$( [ $HT -le 720 ] && echo 8 || echo 16 )
CH=$(( (HT + shb - 1) / shb * shb ))
$D -i $tmp/s.omc -o $tmp/dec.yuv >/dev/null 2>&1
rt=$(python3 $W_/h/rt0.py $tmp/rec.yuv $tmp/dec.yuv $WD $HT $CH $NF $FMT $DP)
bytes=$(stat -c%s $tmp/s.omc)
if [ "$DP" = 10 ]; then
  pf=$( [ "$FMT" = 422 ] && echo yuv422p10le || echo yuv444p10le )
  v=$($W_/h/vmafneg.sh $A $tmp/dec.yuv $WD $HT $NF $pf 2>/dev/null)
else v="n/a"; fi
q=$(python3 $W_/h/quality.py $A $tmp/dec.yuv $WD $HT $NF $FMT $DP)
b=$(python3 $W_/h/blotch.py $A $tmp/dec.yuv $WD $HT $NF --fmt $FMT --sh $shb --depth $DP)
printf "%-4s %-11s %-4s %-4s %-7s rc=%s oob=%-4s %-9s %-12s %s | %s\n" \
  "$T" "${WD}x${HT}" "$FMT" "${DP}b" "${BPP}bpp" "$rc" "$oob" "$rt" "NEG=$v" "$q" "$b"
rm -rf $tmp

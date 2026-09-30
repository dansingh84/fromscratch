#!/bin/bash
# sweep2.sh NAME "flags" "envs" [TREE] -- same as sweep.sh but tree-selectable
W="$(cd "$(dirname "$0")/.." && pwd)"
T=${4:-v5s}
case "$T" in v51) TD=$W/v51/omc_v5.1 ;; *) TD=$W/$T/omc_v5 ;; esac
E=$TD/omc_enc; D=$TD/omc_dec
A=${ARM:-$W/arms/dng_1920x1080_422_10.yuv}
BPP=${BPP:-0.5}; NF=${NF:-6}; FR=${FR:-3}; OUT=${OUT:-$W/diag/arms}
name=$1; flags=$2; envs=$3; mkdir -p $OUT
g=$(env $envs $E -i $A -o $W/out/g_$name.omc -w 1920 -h 1080 --fmt 422 --depth 10 --bpp $BPP -n $NF $flags 2>&1)
oob=$(echo "$g" | grep -oP 'gamut: \K[0-9]+' || echo "?")
rep=$(echo "$g" | grep -oP '\K[0-9]+(?= slices repaired)' || echo 0)
$D -i $W/out/g_$name.omc -o $W/out/g_$name.yuv >/dev/null 2>&1
python3 $W/h/artifactmap.py $A $W/out/g_$name.yuv 1920 1080 $FR $OUT >/dev/null
v=$($W/h/vmafneg.sh $A $W/out/g_$name.yuv 1920 1080 $NF)
q=$(python3 $W/h/quality.py $A $W/out/g_$name.yuv 1920 1080 $NF)
b=$(python3 $W/h/blotch.py $A $W/out/g_$name.yuv 1920 1080 $NF)
echo "$name|oob=$oob|rep=$rep|NEG=$v|$q|$b"

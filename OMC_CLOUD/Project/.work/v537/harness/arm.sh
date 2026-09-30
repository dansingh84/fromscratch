#!/bin/bash
# arm.sh NAME [--flags...] -- ENV=V ...
# Encodes the gfx/DNG arm at 0.5bpp, decodes, and runs the owner-verified detector.
W="$(cd "$(dirname "$0")/.." && pwd)"   # the omc_v5.1 tree root
E=${OMC_ENC:-$W/omc_enc}; D=${OMC_DEC:-$W/omc_dec}
A=${ARM:-$W/arms/dng_1920x1080_422_10.yuv}
BPP=${BPP:-0.5}; NF=${NF:-6}; FR=${FR:-3}
name=$1; shift
encflags=(); while [ "$1" != "--" ] && [ $# -gt 0 ]; do encflags+=("$1"); shift; done; [ $# -gt 0 ] && shift
env "$@" $E -i $A -o $W/out/g_$name.omc -w 1920 -h 1080 --fmt 422 --depth 10 \
    --bpp $BPP -n $NF "${encflags[@]}" 2>&1 | grep -E "gamut|bits/slice" | sed "s/^/[$name] /"
$D -i $W/out/g_$name.omc -o $W/out/g_$name.yuv >/dev/null 2>&1
python3 $W/harness/artifactmap.py $A $W/out/g_$name.yuv 1920 1080 $FR $W/diag/arms

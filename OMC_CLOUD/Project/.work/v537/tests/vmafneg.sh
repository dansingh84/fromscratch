#!/bin/bash
# vmafneg.sh -- VMAF-NEG of a decode against its master.
#
# VMAF-NEG (the "no enhancement gain" model, vmaf_v0.6.1neg) is the metric this
# project judges picture quality by; PSNR is reported alongside it only as a
# second opinion.  libvmaf is not part of the codec drop, so build it first:
#
#   git clone --depth 1 -b v3.0.0 https://github.com/Netflix/vmaf.git /tmp/vmaf_src
#   cd /tmp/vmaf_src/libvmaf && meson setup build --buildtype release \
#       -Denable_asm=false && ninja -C build
#   export VMAF_BIN=/tmp/vmaf_src/libvmaf/build/tools/vmaf
#   export VMAF_MODEL=/tmp/vmaf_src/model/vmaf_v0.6.1neg.json
#
# (-Denable_asm=false avoids needing nasm; the C paths are bit-identical.)
#
#   vmafneg.sh <master.yuv> <decode.yuv> <W> <H> <422|444> <depth>
#
# Both files are planar YUV, 16-bit little-endian words, as everything in
# tests/raw is.  Prints the mean VMAF-NEG over the clip.
set -u
BIN=${VMAF_BIN:-/tmp/vmaf_src/libvmaf/build/tools/vmaf}
MODEL=${VMAF_MODEL:-/tmp/vmaf_src/model/vmaf_v0.6.1neg.json}
M=$1; D=$2; W=$3; H=$4; FMT=$5; DEPTH=$6
[ -x "$BIN" ] || { echo "vmafneg: no libvmaf at $BIN (see the header)"; exit 2; }
[ -f "$MODEL" ] || { echo "vmafneg: no model at $MODEL"; exit 2; }
OUT=$(mktemp)
"$BIN" -r "$M" -d "$D" -w "$W" -h "$H" -p "$FMT" -b "$DEPTH" \
       -m "path=$MODEL" -o "$OUT" --json 2>/dev/null
python3 - "$OUT" <<'PY'
import json, sys
j = json.load(open(sys.argv[1]))
pm = j["pooled_metrics"]
# the neg model's internal name is plain "vmaf"; the score is VMAF-NEG because
# of WHICH model was loaded, not because of what the key is called
k = "vmaf_neg" if "vmaf_neg" in pm else "vmaf"
print("VMAF-NEG mean %.4f  min %.4f  (%d frames)" %
      (pm[k]["mean"], pm[k]["min"], len(j["frames"])))
PY
rm -f "$OUT"

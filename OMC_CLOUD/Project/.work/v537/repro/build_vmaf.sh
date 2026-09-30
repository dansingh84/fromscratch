#!/bin/sh
# Build the VMAF toolchain that Part II's perceptual columns need.
#
# Finding B3: harness/tf_verify.py expects a libvmaf binary and the model JSONs,
# and harness/common.py additionally shells out to qemu-aarch64-static.  Neither
# is in either zip, so "the only external inputs are the two zips" was false for
# every VMAF number in Part II -- which is the metric all of its tuning
# decisions turn on.  This is the exact recipe used for the measurements in this
# document, so the claim becomes true again.
#
# The one non-obvious flag is -Denable_asm=false: libvmaf's x86 assembly needs
# nasm, and a build host without it fails at meson setup rather than falling
# back.  The C paths are bit-identical, only slower.
set -e
VER="${VMAF_VER:-v3.0.0}"
DST="${VMAF_DST:-/tmp/vmaf_src}"

command -v meson >/dev/null || pip install --quiet meson ninja

[ -d "$DST" ] || git clone --depth 1 -b "$VER" https://github.com/Netflix/vmaf.git "$DST"
cd "$DST/libvmaf"
[ -d build ] || meson setup build --buildtype release -Denable_asm=false
ninja -C build

echo
echo "export OMC_VMAF_BIN=$DST/libvmaf/build/tools/vmaf"
echo "export OMC_VMAF_MODELS=$DST/model"
echo
echo "Both models are needed: vmaf_v0.6.1.json and vmaf_v0.6.1neg.json."
echo "harness/tf_verify.py reports BOTH variants for every sequence (C5), and"
echo "the NEG model reports under the key 'vmaf' as well -- it is the model file"
echo "that makes it NEG, which is the documented gotcha."

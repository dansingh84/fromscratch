#!/bin/bash
# cloud_setup.sh — run ONCE from the unpacked OMC_CLOUD/ folder: bash cloud_setup.sh
# 1) rewrites the original absolute project path in every text file to this folder's Project/
# 2) points the VMAF-NEG model path at the bundled model
# 3) builds today's OMC codec (read-only reference) and checks the tools
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
NEW="$HERE/Project"
OLD="/home/dan/Documents/Apps/Codec/Project"
echo "== rewriting $OLD -> $NEW in text files"
grep -rlI --exclude='*.omc' -e "$OLD" "$NEW" | while read -r f; do sed -i "s#$OLD#$NEW#g" "$f"; done
echo "== VMAF model path"
MODEL="$HERE/vmaf_model/vmaf_v0.6.1neg.json"
grep -rlI "/usr/share/model/vmaf_v0.6.1neg.json" "$NEW" | while read -r f; do sed -i "s#/usr/share/model/vmaf_v0.6.1neg.json#$MODEL#g" "$f"; done
echo "== scratch dir (many scripts use \$SCR or /tmp); set TMPDIR if /tmp is small"
mkdir -p "$HERE/scratch"
echo "== building today's codec (reference only; never modify .work/v537)"
( cd "$NEW/.work/v537" && make omc_enc omc_dec -j4 >/dev/null && echo "built omc_enc omc_dec" )
echo "== checks"
python3 -c "import numpy; print('numpy', numpy.__version__)"
ffmpeg -hide_banner -filters 2>/dev/null | grep -q libvmaf && echo "ffmpeg libvmaf: OK" || echo "!! ffmpeg WITHOUT libvmaf — install an ffmpeg built with libvmaf (VMAF-NEG is the primary metric)"
echo "== next: put the footage under $NEW/.work/arms/ (see CLOUD_README.md §3), then: bash regen_today.sh"

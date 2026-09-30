#!/bin/bash
# regen_today.sh — rebuild today's REAL decodes (the comparison baseline) from the bundled bitstreams.
# Verified 2026-09-29: omc_dec on these .omc files reproduces the original .d.yuv byte for byte.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
P="$HERE/Project"
DEC="$P/.work/v537/omc_dec"
[ -x "$DEC" ] || { echo "run cloud_setup.sh first"; exit 1; }
for d in "$P/Subagents/SA7_legality_v2/out/DM" "$P/Subagents/SA15_design/out/today"; do
  for f in "$d"/*.omc; do
    out="${f%.omc}.d.yuv"
    [ -s "$out" ] && continue
    "$DEC" -i "$f" -o "$out" >/dev/null 2>&1 && echo "ok $(basename "$out")" || echo "FAILED $(basename "$f")"
  done
done
echo "today's decodes ready"

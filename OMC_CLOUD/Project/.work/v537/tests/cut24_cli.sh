#!/bin/bash
# [V537-BUDGET] G-T5-CUT24-CLI: the SHIPPED command-line encoder, at its default, commits no out-of-range
# sample on the 24-frame rail-plate cut sequence at the shipped refresh period; and the gate is
# non-vacuous: the same run at --gamut-strict 12 (the v5.3.5 budget) must still leak.  Exists because
# the in-process suite (GM_PASS) cannot see what tools/omc_enc.c passes to the library -- v5.3.6
# shipped a CLI default of 12 while the suite tested 13.
set -u
# --bpp is bits per LUMA pixel: 2.0 gives bits_per_slice = 2 * W * SH = 8192, the figure tests/test_xsl.c sets directly (its comment says "1.0 bpp on luma pixels" and means per SAMPLE).
D="$(cd "$(dirname "$0")/.." && pwd)"; T="${TMPDIR:-/tmp}/omc_cut24_$$"; mkdir -p "$T"; trap 'rm -rf "$T"' EXIT
"$D/test_xsl" --dump-cut24 "$T/cut24.yuv" > /dev/null || { echo "G-T5-CUT24-CLI FAIL: could not write the arm"; exit 1; }
run() { "$D/omc_enc" -i "$T/cut24.yuv" -o "$T/o.omc" -w 256 -h 64 --fmt 422 --depth 10 --bpp 2.0 -n 24 --recon "$T/r.yuv" "$@" > "$T/e.log" 2>&1; echo "$? $(grep -o 'gamut: [0-9]* committed' "$T/e.log" | grep -o '[0-9]*')"; }
def=$(run); old=$(run --gamut-strict 12)
set -- $def; drc=$1; doob=${2:-?}; set -- $old; orc=$1; ooob=${2:-?}
if [ "$doob" = 0 ] && [ "$drc" = 0 ]; then
  if [ "$ooob" != 0 ] && [ "$ooob" != "?" ]; then
    echo "ok: G-T5-CUT24-CLI the shipped omc_enc at its default commits 0 out-of-range samples on the cut sequence (rc 0), and at --gamut-strict 12 it still leaks $ooob (rc $orc): the CLI runs the library's budget and the gate bites"
  else echo "FAIL: G-T5-CUT24-CLI vacuous: --gamut-strict 12 leaked '$ooob' (expected > 0)"; exit 1; fi
else echo "FAIL: G-T5-CUT24-CLI the shipped omc_enc leaks $doob out-of-range samples (rc $drc) at its default"; exit 1; fi

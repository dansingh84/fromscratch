#!/bin/bash
# levercheck.sh -- every documented lever must ACT where it is supposed to, be
# INERT where it is supposed to stand down, and read-only instruments must never
# touch the stream.
#
# sect.11.5d M1: a mechanical rewrite once produced
#     const int gm_mode_eff = (...) ? 12 : gm_mode_eff;
# a self-referential initialiser that compiled clean at -O2 and made every mode
# comparison in the repair read garbage.  Two full measurement rounds were
# published internally before byte-comparison caught it -- a gate run reporting
# "ALL GATES PASS" for configurations that in fact FAIL, and a corpus battery
# reporting every arm identical to the shipped build.  The rule that came out of
# it -- "verify the lever ACTS before believing any measurement taken with it" --
# is weaker than a check.  This is the check.
#
# It needs BOTH slice-height rungs, because several v5.3 levers are geometry-
# conditional by design (sect.55.8b): the seam cascade and the chroma dead-band
# stand down at slice_h <= 8, and OMC_FILLREACH's auto rule already yields 64
# there.  Running only one rung reports those stand-downs as dead code.
#
#   usage: tests/levercheck.sh TALL.yuv W H FMT DEPTH BPP  SHORT.yuv W H FMT DEPTH BPP
#          TALL  must resolve to slice_h >= 16 (e.g. a 1080p arm)
#          SHORT must resolve to slice_h <= 8  (e.g. a 720p or 448x256 arm)
set -u
ENC=${OMC_ENC:-./omc_enc}
[ $# -ge 12 ] || { echo "levercheck: usage: tests/levercheck.sh TALL.yuv W H FMT DEPTH BPP SHORT.yuv W H FMT DEPTH BPP" >&2; exit 2; }
[ -x "$ENC" ] || { echo "levercheck: no encoder at $ENC" >&2; exit 2; }
T=$(mktemp -d "${TMPDIR:-/tmp}/lchk_XXXXXX"); trap 'rm -rf "$T"' EXIT
TA=$1 TW=$2 TH=$3 TF=$4 TD=$5 TB=$6
SA=$7 SW=$8 SH=$9 SF=${10} SD=${11} SB=${12}
enc() { # $1 env, $2.. arm geometry
  env $1 "$ENC" -i "$2" -o "$T/o.omc" -w $3 -h $4 --fmt $5 --depth $6 --bpp $7 -n 4 >/dev/null 2>&1
  md5sum < "$T/o.omc" 2>/dev/null | cut -d' ' -f1
}
BT=$(enc "" "$TA" $TW $TH $TF $TD $TB)
BS=$(enc "" "$SA" $SW $SH $SF $SD $SB)
[ -n "$BT" ] && [ -n "$BS" ] || { echo "levercheck: a baseline encode failed" >&2; exit 2; }
fail=0; n=0
chk() { # $1 lever  $2 arm-tag  $3 expect(act|inert)
  local L=$1 tag=$2 want=$3 h
  n=$((n+1))
  if [ "$tag" = tall ]; then h=$(enc "$L" "$TA" $TW $TH $TF $TD $TB); [ "$h" = "$BT" ] && got=inert || got=act
  else h=$(enc "$L" "$SA" $SW $SH $SF $SD $SB); [ "$h" = "$BS" ] && got=inert || got=act; fi
  [ -z "$h" ] && { echo "FAIL: levercheck $L ($tag) -- the encoder produced no stream"; fail=$((fail+1)); return; }
  if [ "$got" != "$want" ]; then
    echo "FAIL: levercheck $L on the $tag rung -- expected $want, got $got."
    [ "$want" = act ] && echo "      INERT means the lever is dead code or an edit broke it; no measurement" \
                      && echo "      taken with it is meaningful (sect.11.5d M1)."
    [ "$want" = inert ] && echo "      This lever is supposed to STAND DOWN at slice_h <= 8 (sect.55.8b)."
    fail=$((fail+1))
  fi
}
# --- levers that must act on BOTH rungs
for L in OMC_GM_MODE=12 OMC_GM_ESCMODE=0 OMC_GM_UPSTEP=32 OMC_GM_BITEFF=1 \
         OMC_XSL_CASC=1 OMC_Q5FLAG=0 OMC_GM_VETOAT=0 OMC_XSL_LOOPFREE=0 \
         OMC_PLAN_HYST=2 OMC_FILLGHYS=1; do
  chk "$L" tall act; chk "$L" short act
done
# --- geometry-conditional: act on the tall rung, stand down on the short one
for L in OMC_XSL_SPREAD=2 OMC_FILLTHYS_C=0 OMC_FILLTHYS=3 OMC_FILLTHYS_NB=0 OMC_FILLREACH=64; do
  chk "$L" tall act; chk "$L" short inert
done
# --- read-only instruments must never touch the stream, on either rung
for L in OMC_Q5LIVE=1 OMC_Q5STAT=1 OMC_GM_STAT=1; do
  chk "$L" tall inert; chk "$L" short inert
done
if [ $fail -eq 0 ]; then
  echo "ok: levercheck -- $n checks: every lever acts where it should, every stand-down holds, every read-only instrument is byte-inert"
else
  echo "levercheck: $fail of $n FAILED"; exit 1
fi

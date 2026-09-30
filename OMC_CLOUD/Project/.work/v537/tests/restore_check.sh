#!/bin/bash
# G-T5-RESTORE — the v5.0 restore switch is VERIFIED, not asserted.
#
# v5.1 changes ONLY encoder policy, and every change sits behind an environment
# lever that restores v5.0 exactly when cleared.  That claim is the non-vacuity
# proof for the whole release (docs/OMC_V5_1.md sect.7.2, README.md,
# CHANGELOG_v5.1.md), and until v5.1 it was checked by hand.
#
# It rotted exactly once, immediately, which is why this gate exists: when
# OMC_GM_VETO's default moved from 2 to 1 (ledger sect.51.16) the documented
# incantation was not updated with it, and silently stopped restoring v5.0.
# The documentation still said "verified byte-identical".  Adding a new
# default-changing lever without adding it to the incantation now fails here.
#
# ---- v5.3: THE GATE ITSELF WAS CONFLATING TWO THINGS (ledger sect.11.5d D12).
#
# It compared the whole stream byte-for-byte, so a DELIBERATE stream-version
# bump made it unpassable no matter how correct the restore switch was.  v5.3
# moves OMC_MINOR_T5 12 -> 13 (sect.11.6), and with the incantation complete
# the emitted stream differed from the reference vector in EXACTLY ONE BYTE --
# header byte 6, the minor.  345 631 of 345 632 bytes matched.
#
# So the gate now checks the two claims separately, which is what it should
# always have done:
#   (1) the restore switch reproduces v5.0's RECONSTRUCTION -- every byte
#       outside the version field is identical;
#   (2) the version field says what THIS release says it should say.
# A stale incantation still fails (1).  A version bump that the build did not
# intend still fails (2).  Neither can mask the other any more.
#
# SELF-CONTAINED BY CONSTRUCTION.  It needs no footage: the cell is generated
# by tests/mkrail.py, which is deterministic and uses no RNG, and the reference
# stream delivery/conformance/vectors/c5_v50_restore_rail.omc was produced from
# that same generated cell by a PRISTINE v5.0 encoder.  The cell is rail-heavy
# on purpose -- it drives 293 slice repairs and 93 falls back to the harsh
# rule, so it exercises every branch the v5.1 levers touch.  A cell the repair
# never fires on would pass this gate no matter what the levers did.
#
#   usage: tests/restore_check.sh
set -u
D="$(cd "$(dirname "$0")/.." && pwd)"
# ---- v5.3.6: RE-BASED ON A v5.3.6 GOLDEN VECTOR (docs/CHANGES_v5_3_6.md sect.B).
#
# The v5.0 byte-restore claim ended at minor 15: the lifting rounding ([S5-DC]), coefficient
# saturation, the block motion field (16) and the level-2 boundary predictor (17) are NORMATIVE
# transform changes no encoder lever can undo.  Measured on 2026-09-08 with the vectors restored:
# 239,662 bytes differ against c5_v50_restore_rail.omc outside the version field -- not a stale
# incantation.  So the reference is now c536_policy_restore_rail.omc, produced by THIS release's
# encoder under the incantation below.  Check (1) still catches an unlisted default change in any
# later build (the reason this gate exists); check (2) is unchanged.  The v5.0 vector stays in the
# folder as history.  OMC_VEXT / OMC_VEXT_LVL are deliberately NOT in the incantation: they are
# normative in minor 17, not encoder policy, and the decoder pins them.
REF="$D/delivery/conformance/vectors/c536_policy_restore_rail.omc"
TD="${TMPDIR:-/tmp}"
CELL="$TD/omc_restore_cell_$$.yuv"
OUT="$TD/omc_restore_out_$$.omc"
trap 'rm -f "$CELL" "$OUT"' EXIT

[ -f "$REF" ] || { echo "G-T5-RESTORE FAIL: reference vector missing: $REF (regenerate ONLY with a release encoder: tests/restore_mkref.sh)"; exit 1; }
[ -x "$D/omc_enc" ] || { echo "G-T5-RESTORE FAIL: omc_enc not built"; exit 1; }

python3 "$D/tests/mkrail.py" "$CELL" 1280 720 10 6 >/dev/null 2>&1 || {
    echo "G-T5-RESTORE FAIL: could not generate the cell (needs python3 + numpy)"
    exit 1; }

# ---- the incantation, copied VERBATIM from README.md / CHANGELOG_v5.1.md ----
OMC_GM_PLANRESET=0 OMC_GM_INTRAEVID=0 OMC_GM_INTRAFROM=1 OMC_GM_MODE=12 \
OMC_GM_LLCAP=0 OMC_GM_LLHARD=0 OMC_GM_LLDENSE=0 OMC_GM_LOOPNEED=0 \
OMC_GM_LLBND=1 OMC_GM_RETRO=1 OMC_GM_HARDMIN=1 OMC_GM_DETFLOOR=0 \
OMC_GM_DROPINTRA=0 OMC_GM_INTRASTICKY=1 OMC_GM_INTERABS=0 OMC_GM_VETO=2 \
OMC_FILL=0 OMC_FILLINTRA=0 OMC_ANTSGATE=24 OMC_FILLTHR=3 OMC_FILLDIV=0 \
OMC_GM_ESCMODE=0 OMC_GM_VETOAT=0 OMC_Q5FLAG=0 OMC_XSL_LOOPFREE=0 \
OMC_FILLREACH=0 OMC_FILLTHYS_C=0 OMC_PLAN_HYST=0 OMC_RBOOST=0 OMC_PLANSD=0 OMC_GM_DILFROM=0 OMC_LOCK_TIEACT=0 OMC_GM_LATT=0 \
"$D/omc_enc" -i "$CELL" -o "$OUT" -w 1280 -h 720 --fmt 422 --depth 10 \
             --bpp 0.5 -n 6 >/dev/null 2>&1
rc=$?
[ $rc -eq 0 ] || { echo "G-T5-RESTORE FAIL: omc_enc exited $rc"; exit 1; }

# --- (1) reconstruction: identical everywhere EXCEPT the version field.
# --- (2) version field: exactly what this build's OMC_MINOR_T5 says.
MIN=$(grep -oE '#define OMC_MINOR_T5 [0-9]+' "$D/include/omc1.h" | grep -oE '[0-9]+$')
VERDICT=$(python3 - "$OUT" "$REF" "${MIN:-0}" <<'PYEOF'
import sys
out, ref, want = open(sys.argv[1],'rb').read(), open(sys.argv[2],'rb').read(), int(sys.argv[3])
if len(out) != len(ref):
    print("LEN %d %d" % (len(out), len(ref))); raise SystemExit
MINOR = 5                                  # header byte index of the stream minor
diff = [i for i in range(len(out)) if out[i] != ref[i]]
body = [i for i in diff if i != MINOR]
print("BODY %d MINOR %d WANT %d REFMINOR %d" % (len(body), out[MINOR], want, ref[MINOR]))
PYEOF
)
set -- $VERDICT
if [ "$1" = LEN ]; then
    echo "G-T5-RESTORE FAIL: stream length changed ($2 vs $3) -- this is not a"
    echo "                   version-field difference, the restore switch is broken."
    exit 1
fi
BODY=$2; GOTMIN=$4; WANTMIN=$6; REFMIN=$8
if [ "$BODY" -eq 0 ] && [ "$GOTMIN" = "$WANTMIN" ]; then
    if [ "$GOTMIN" = "$REFMIN" ]; then
        echo "G-T5-RESTORE ok: the documented lever incantation reproduces this release's"
        echo "                 golden vector byte-for-byte (v5.3.6 re-base; 293 repaired slices)"
    else
        echo "G-T5-RESTORE ok: the documented lever incantation reproduces the golden"
        echo "                 vector's RECONSTRUCTION exactly -- every byte outside the version"
        echo "                 field is identical (293 repaired slices).  The stream"
        echo "                 minor is $GOTMIN where the reference vector carries $REFMIN,"
        echo "                 which is this release's intended bump, not a defect."
    fi
    exit 0
fi
if [ "$BODY" -ne 0 ]; then
    cat <<MSG
G-T5-RESTORE FAIL: the restore switch no longer reproduces v5.0's
                   reconstruction -- $BODY bytes differ OUTSIDE the version
                   field.  Most likely a lever's shipped default changed and
                   the incantation above was not updated with it.
MSG
else
    echo "G-T5-RESTORE FAIL: the emitted stream minor is $GOTMIN but this build's"
    echo "                   OMC_MINOR_T5 is $WANTMIN.  The header does not say what"
    echo "                   the build says."
fi
cat <<'MSG2'
                   Diff src/codec.c's getenv defaults against the list in
                   README.md, CHANGELOG_v5.3.md, docs/OMC_V5_1.md sect.7.2 and
                   the defaults table in docs/CONTROL_PLANE.md -- all must agree.
MSG2
exit 1
cat <<'MSG'
G-T5-RESTORE FAIL: the documented restore incantation no longer produces v5.0
                   bytes.  Most likely a lever's shipped default changed and the
                   incantation was not updated.  Diff src/codec.c's getenv
                   defaults against the list in README.md, CHANGELOG_v5.1.md,
                   docs/OMC_V5_1.md sect.7.2 and the defaults table in
                   docs/CONTROL_PLANE.md -- all five must agree.
MSG
exit 1

#!/bin/bash
# refcheck.sh -- every "sect.N" citation in the source must resolve to a real
# ledger heading.
#
# ledger sect.11.5d D5: the shipped source cited "sect.82" four times and no
# such section has ever existed.  A comment that cites a section nobody can find
# stops being trustworthy, and there is no compiler for that.  This is the
# compiler for that.
#
# 2026-08-30: seven citations are PRE-EXISTING and unresolved.  They are listed
# below rather than suppressed, so they stay visible and so a NEW one fails
# immediately instead of joining them.
#
#   usage: tests/refcheck.sh [LEDGER.md]
set -u
D="$(cd "$(dirname "$0")/.." && pwd)"
L="${1:-$D/LEDGER_v5_ADVERSARIAL.md}"
[ -f "$L" ] || { echo "SKIP: refcheck -- no ledger at $L"; exit 0; }
KNOWN="51.5b 51.5c 51.5d 51.5e 51.5f 51.5g 67.13"
# The ledger also cites ITSELF.  These are unresolved and PRE-EXISTING; several
# (12.22.*) are cross-document references into docs/TEMPORAL_T5.md and are fine.
# Listed so a NEW self-reference fails instead of joining them.
KNOWN_LEDGER="12.22 12.22.3 12.22.3g 12.22.3i 12.22.3j 12.22.8 12.20 12.23 18.6 18.7 3.2 836 \
21 21.4 3.7 35.4 36 36.1 38.2a 45.3 51.5f 54.8 7.5 78.4b 9.5"
python3 - "$D/src/codec.c" "$L" "$KNOWN" "$KNOWN_LEDGER" <<'PYEOF'
import re, sys
src, led = open(sys.argv[1],encoding='utf-8').read(), open(sys.argv[2],encoding='utf-8').read()
known, known_led = set(sys.argv[3].split()), set(sys.argv[4].split())
heads=set()
for m in re.finditer(r'^#{1,4} (?:sect\.)?([0-9]+(?:\.[0-9a-z]+)*)[ .]', led, re.M): heads.add(m.group(1))
cited=set(re.findall(r'sect\.([0-9]+(?:\.[0-9a-z]+)*)', src))
bad=[c for c in sorted(cited) if not any(h==c or h.startswith(c+'.') for h in heads)]
new=[c for c in bad if c not in known]
stale=[c for c in sorted(known) if c not in bad]
if new:
    print("FAIL: refcheck -- source cites ledger sections that do not exist:")
    for c in new: print("        sect.%s" % c)
    print("      Either write the section, or repoint the comment at the section that")
    print("      actually holds the material (ledger sect.11.5d D5).")
    raise SystemExit(1)
# the ledger's own internal cross-references
lrefs=set(re.findall(r'\u00a7([0-9]+(?:\.[0-9a-z]+)*)', led))
lbad=[c for c in sorted(lrefs) if not any(h==c or h.startswith(c+'.') for h in heads)]
lnew=[c for c in lbad if c not in known_led]
if lnew:
    print("FAIL: refcheck -- the LEDGER cites sections of itself that do not exist:")
    for c in lnew: print("        \u00a7%s" % c)
    print("      Write the section, or repoint the reference at the one that holds the")
    print("      material (ledger sect.11.5d D16).")
    raise SystemExit(1)
msg = "ok: refcheck -- all %d cited sections resolve" % (len(cited)-len(bad))
if bad: msg += "; %d PRE-EXISTING unresolved and still open: %s" % (len(bad), " ".join("sect."+c for c in bad))
if stale: msg += "  [allow-list is stale, these now resolve: %s]" % " ".join(stale)
if lbad: msg += "; ledger self-refs unresolved (pre-existing): %d" % len(lbad)
print(msg)
PYEOF

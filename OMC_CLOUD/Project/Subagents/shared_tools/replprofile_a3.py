#!/usr/bin/env python3
"""[A3] Row-replication rate for EVERY row-in-slice, not a pre-chosen pair.

replication_a3.py measures a fixed pair (rows 13-14, from dwt.c sect.55).  That
was right for characterising the mirror's degeneracy, but it is the wrong
instrument for judging a change to the TERMINAL pair (14,15): an instrument that
looks at rows 13-14 while the change acts on rows 14-15 can credit or blame the
change for the wrong reason.  This reports the whole profile so the attribution
is visible rather than assumed.

repl(r) = fraction of samples where decode row r equals decode row r-1.
The source's own profile is printed beside it: source content replicates too,
and only the EXCESS over source is an artifact.

usage: replprofile_a3.py SRC DEC W H FMT DEPTH FRAME [SH]"""
import sys, numpy as np
src, dec = sys.argv[1], sys.argv[2]
W, H = int(sys.argv[3]), int(sys.argv[4]); fmt = sys.argv[5]
dep, fr = int(sys.argv[6]), int(sys.argv[7])
sh = int(sys.argv[8]) if len(sys.argv) > 8 else (8 if H <= 720 else 16)
cw = W if fmt == '444' else W // 2
fw = W * H + 2 * cw * H
dt = '<u2' if dep > 8 else 'u1'
def load(p):
    d = np.fromfile(p, dtype=dt, count=(fr + 1) * fw)[fr * fw:(fr + 1) * fw]
    if d.size < fw: raise SystemExit("  replprofile: frame not present")
    return d[:W*H].reshape(H, W)
s, d = load(src), load(dec)
srp, drp = [], []
for ph in range(sh):
    rows = [r for r in range(1, H) if r % sh == ph]
    srp.append(float(np.mean([np.mean(s[r] == s[r-1]) for r in rows])))
    drp.append(float(np.mean([np.mean(d[r] == d[r-1]) for r in rows])))
print("   phase : " + " ".join(f"{p:6d}" for p in range(sh)))
print("   source: " + " ".join(f"{v:6.3f}" for v in srp))
print("   decode: " + " ".join(f"{v:6.3f}" for v in drp))
print("   excess: " + " ".join((f"{d_/s_:5.1f}x" if s_ > 0.0005 else "   -  ")
                               for s_, d_ in zip(srp, drp)))

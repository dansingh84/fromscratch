#!/usr/bin/env python3
"""[A3] mean |decode - source| by ROW-IN-SLICE, for ALL THREE PLANES.

rowphase_a3.py reports luma only.  The codec expert's third reply warned that
the row-class model holds on luma and fails on chroma, and that any boundary
rule must be "luma-first, separately measured for Cb and Cr, never assumed to
transfer".  A luma-only instrument cannot see that, so it cannot qualify a
transform change that touches all three planes.

Chroma vertical resolution equals luma in 4:2:2 and 4:4:4 (both keep full
height), so the slice grid maps to chroma rows one-for-one and the same slice
phase applies.  Widths differ; that only affects the row means, not the phase.

usage: rowphase3_a3.py SRC DEC W H FMT DEPTH FRAME [SH]"""
import sys, numpy as np
src, dec = sys.argv[1], sys.argv[2]
W, H = int(sys.argv[3]), int(sys.argv[4]); fmt = sys.argv[5]
dep, fr = int(sys.argv[6]), int(sys.argv[7])
sh = int(sys.argv[8]) if len(sys.argv) > 8 else (8 if H <= 720 else 16)
cw = W if fmt == '444' else W // 2
fw = W * H + 2 * cw * H
dt = '<u2' if dep > 8 else 'u1'
def load(p):
    d = np.fromfile(p, dtype=dt, count=(fr + 1) * fw)[fr * fw:(fr + 1) * fw].astype(np.float64)
    if d.size < fw: raise SystemExit(f"  rowphase3: frame {fr} not present in {p}")
    return (d[:W*H].reshape(H, W),
            d[W*H:W*H+cw*H].reshape(H, cw),
            d[W*H+cw*H:].reshape(H, cw))
a = load(src); b = load(dec)
out = []
for nm, pa, pb in zip(("Y", "Cb", "Cr"), a, b):
    e = np.abs(pa - pb)
    rows = e.mean(axis=1)
    nsl = H // sh
    prof = np.array([rows[p::sh][:nsl].mean() for p in range(sh)])
    m = prof.mean()
    if m == 0:
        out.append(f"{nm}: exact"); continue
    out.append(f"{nm}: last-row {100*(prof[-1]/m-1):+.1f}% spread {100*(prof.max()-prof.min())/m:.1f}% mean {m:.3f}")
print("  rowphase3 f%d | " % fr + " | ".join(out))

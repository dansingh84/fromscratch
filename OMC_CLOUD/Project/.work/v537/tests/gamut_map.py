#!/usr/bin/env python3
"""gamut_map.py - WHERE the out-of-range committed samples are, not just how many.

The hand-off report asked whether stray samples cluster, and in particular
whether they sit on slice boundaries.  This answers it from a decoded CDR (the
committed picture, biased by 2048 and unclipped, at coded geometry):

  gamut_map.py <file.cdr> <W> <H> <422|444> <depth> <slice_h> [display_h]

Prints the count per plane, the histogram over row-within-slice (so a boundary
concentration is visible at once), the share that sit in the two rows the XSL
boundary edit touches, and the size distribution of connected runs along a row
(1 = isolated samples, larger = clustered).
"""
import sys, numpy as np

f, W, H, fmt, depth, sh = (sys.argv[1], int(sys.argv[2]), int(sys.argv[3]),
                           sys.argv[4], int(sys.argv[5]), int(sys.argv[6]))
dh = int(sys.argv[7]) if len(sys.argv) > 7 else H
Wc = W if fmt == '444' else W // 2
maxv = (1 << depth) - 1
BIAS = 2048
fw = W * H + 2 * Wc * H
a = np.fromfile(f, dtype='<u2')
assert a.size % fw == 0, "not a whole number of frames at this geometry"
nf = a.size // fw
a = a.reshape(nf, fw)

names = ["Y", "Cb", "Cr"]
rowhist = np.zeros(sh, dtype=np.int64)
runhist = {}
total = 0
for p in range(3):
    pw = W if p == 0 else Wc
    off = 0 if p == 0 else W * H + (p - 1) * Wc * H
    n = 0
    for k in range(nf):
        pl = a[k, off:off + pw * H].reshape(H, pw)[:dh]
        bad = (pl.astype(np.int32) - BIAS < 0) | (pl.astype(np.int32) - BIAS > maxv)
        n += int(bad.sum())
        rows = np.nonzero(bad.any(axis=1))[0]
        for r in rows:
            rowhist[r % sh] += int(bad[r].sum())
            # run lengths along the row
            b = bad[r].astype(np.int8)
            d = np.diff(np.concatenate(([0], b, [0])))
            for s, e in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
                runhist[e - s] = runhist.get(e - s, 0) + 1
    print("%-3s %d samples outside [0..%d]" % (names[p], n, maxv))
    total += n
print("total %d over %d frame(s)" % (total, nf))
if total:
    print("row within slice (0 .. %d):" % (sh - 1))
    for r in range(sh):
        if rowhist[r]:
            print("  row %2d: %8d  (%.1f%%)" % (r, rowhist[r], 100.0 * rowhist[r] / total))
    edge = rowhist[0] + rowhist[sh - 1]
    print("in the two rows the XSL boundary edit touches (0 and %d): %d (%.1f%%)"
          % (sh - 1, edge, 100.0 * edge / total))
    print("expected if spread evenly over rows: %.1f%%" % (200.0 / sh))
    print("run lengths along a row:")
    for L in sorted(runhist):
        print("  %3d px: %6d run(s)" % (L, runhist[L]))

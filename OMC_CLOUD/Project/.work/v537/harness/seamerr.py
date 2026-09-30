#!/usr/bin/env python3
"""seamerr.py SRC DEC W H NFRAMES [--fmt][--depth][--sh 16][--label X]

A HORIZONTAL LINE IS A ROW-TO-ROW STEP THE SOURCE DOES NOT HAVE.

An earlier version of this instrument compared the MAGNITUDE of the decode's
row-to-row step at the slice seam against its magnitude in the slice interior,
and read a ratio of 2.13 as "the seam is twice too strong".  That was wrong,
and the source column is what showed it: OMC's interior Cb step is 5.7 where
the SOURCE's is 16.6, so the interior is over-smoothed by a factor of three and
the seam, at 12.2, is the one place still carrying something like the true
vertical variation.  Chasing the ratio would have meant softening the most
faithful rows in the picture.

So this measures the ERROR instead, per row phase and per plane:

    dstep(r) = mean over the row of | (dec[r] - dec[r-1]) - (src[r] - src[r-1]) |

which is zero wherever the decode's vertical structure matches the source's,
whatever its magnitude.  A horizontal line is a phase where dstep spikes.
Reported as the phase profile, its spread, and the single number

    LINE = max over phases of dstep(phase) / median over phases of dstep

which is 1.0 when no row phase is special and rises with any structure locked
to the coding grid.  A signed version is also printed, because a step that is
consistently too LARGE (an exaggerated edge) and one consistently too SMALL (a
smoothed-away edge) are different defects with different fixes.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio

a = sys.argv
src, dec, W, H, N = a[1], a[2], int(a[3]), int(a[4]), int(a[5])
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
lab   = a[a.index('--label')+1]      if '--label' in a else os.path.basename(dec)

ab = np.zeros((3, sh)); sg = np.zeros((3, sh)); cnt = np.zeros(sh)
for f in range(N):
    S = yuvio.planes(src, W, H, f, fmt, depth)
    D = yuvio.planes(dec, W, H, f, fmt, depth)
    for i in range(3):
        ds = D[i][1:] - D[i][:-1]
        ss = S[i][1:] - S[i][:-1]
        e = ds - ss
        for r in range(1, D[i].shape[0]):
            ab[i, r % sh] += float(np.abs(e[r-1]).mean())
            sg[i, r % sh] += float((np.abs(ds[r-1]) - np.abs(ss[r-1])).mean())
    for r in range(1, H):
        cnt[r % sh] += 1
ab /= np.maximum(cnt, 1); sg /= np.maximum(cnt, 1)
print("%s   row phase inside the %d-row slice" % (lab, sh))
print("   phase:" + "".join("%7d" % p for p in range(sh)))
for i, nm in enumerate(("Y ", "Cb", "Cr")):
    med = float(np.median(ab[i]))
    print("   %s dstep :" % nm + "".join("%7.2f" % v for v in ab[i])
          + "   LINE %5.2f" % (ab[i].max() / max(med, 1e-9)))
    print("   %s signed:" % nm + "".join("%+7.2f" % v for v in sg[i]))

#!/usr/bin/env python3
"""rowdup.py SRC DEC W H NFRAMES [--fmt][--depth][--sh 16][--label X]

ROW REPLICATION BY ROW PHASE -- the direct test of the last-row mechanism.

The vertical 5/3 inverse reconstructs an odd row as

    x[2i+1] = H[i] + ((x[2i] + x[2i+2]) >> 1)

except for the LAST pair of the slice, where the symmetric extension makes
x[2i+2] read x[2i], so it degenerates to

    x[last] = H[last] + x[last-1]

When H is quantised to zero -- which is the common case at 0.5 bpp on a
low-energy plane -- every interior odd row becomes the AVERAGE of its two
neighbours, which is a smooth interpolation, while the last row of the slice
becomes an EXACT COPY of the row above it.

That predicts two things this script measures, per plane and per row phase:

  dup    the fraction of samples exactly equal to the sample directly above.
         Should spike at the last phase, and only there.
  step   the mean |difference| across the boundary to the NEXT row.  A
         replicated row pushes the whole step into the slice seam, so this
         should spike at the last phase too -- which is the same defect wearing
         its other face, a horizontal line at the slice pitch.

The SOURCE's own profile is printed beside the decode's, because some content
genuinely repeats rows and a raw rate would be read wrong without that null.
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

dup = np.zeros((2, 3, sh)); step = np.zeros((2, 3, sh)); cnt = np.zeros(sh)
for f in range(N):
    for k, path in enumerate((src, dec)):
        P = yuvio.planes(path, W, H, f, fmt, depth)
        for i in range(3):
            p = P[i]; h = p.shape[0]
            eq = (p[1:] == p[:-1])
            df = np.abs(p[1:] - p[:-1])
            for r in range(1, h):
                dup[k, i, r % sh] += float(eq[r-1].mean())
                step[k, i, r % sh] += float(df[r-1].mean())
    for r in range(1, H):
        cnt[r % sh] += 1
dup /= np.maximum(cnt, 1); step /= np.maximum(cnt, 1)
print("%s   row phase inside the %d-row slice   (SRC row shown for the null)" % (lab, sh))
print("   phase:" + "".join("%7d" % p for p in range(sh)))
for i, nm in enumerate(("Y ", "Cb", "Cr")):
    print("   %s dup DEC:" % nm + "".join("%7.3f" % v for v in dup[1, i]))
    print("   %s dup SRC:" % nm + "".join("%7.3f" % v for v in dup[0, i]))
    print("   %s step DEC:" % nm + "".join("%7.2f" % v for v in step[1, i]))
    print("   %s step SRC:" % nm + "".join("%7.2f" % v for v in step[0, i]))

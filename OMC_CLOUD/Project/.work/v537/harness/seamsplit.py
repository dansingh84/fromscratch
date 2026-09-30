#!/usr/bin/env python3
"""seamsplit.py SRC DEC W H NFRAMES [--fmt][--depth][--sh 16][--label X]

IS THE SEAM A DC MISMATCH OR A TEXTURE MISMATCH?

The two have different fixes and the same appearance.  A horizontal line at the
slice pitch can be

  DC       adjacent slices quantised their LEVEL (the LL band) independently and
           landed on different rungs, so the whole row jumps.  The fix belongs
           in the LL / cross-slice term.
  TEXTURE  the levels agree but the amount of DETAIL changes abruptly across the
           boundary -- one slice's last rows are smoothed and the next slice's
           first rows are not.  The fix belongs in the vertical transform or in
           the allocation.

So the row-to-row error is split into its two parts, per plane:

  DC part      | mean over the row of (dec[r]-dec[r-1]) - (src[r]-src[r-1]) |
               -- the row-mean step error, which survives only if the whole row
               moves together
  AC part      the row's standard deviation of the same quantity
               -- what is left when the common movement is removed

and each is profiled by row phase.  The seam's EXCESS over the interior median
is reported for both, so the two mechanisms can be ranked rather than guessed.
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

dc = np.zeros((3, sh)); ac = np.zeros((3, sh)); cnt = np.zeros(sh)
for f in range(N):
    S = yuvio.planes(src, W, H, f, fmt, depth)
    D = yuvio.planes(dec, W, H, f, fmt, depth)
    for i in range(3):
        e = (D[i][1:] - D[i][:-1]) - (S[i][1:] - S[i][:-1])
        for r in range(1, D[i].shape[0]):
            row = e[r-1]
            dc[i, r % sh] += abs(float(row.mean()))
            ac[i, r % sh] += float(row.std())
    for r in range(1, H):
        cnt[r % sh] += 1
dc /= np.maximum(cnt, 1); ac /= np.maximum(cnt, 1)
print("%s   slice_h %d" % (lab, sh))
for i, nm in enumerate(("Y ", "Cb", "Cr")):
    dmed = float(np.median(dc[i])); amed = float(np.median(ac[i]))
    print("   %s DC :" % nm + "".join("%7.2f" % v for v in dc[i])
          + "   seam/med %5.2f" % (dc[i][0] / max(dmed, 1e-9)))
    print("   %s AC :" % nm + "".join("%7.2f" % v for v in ac[i])
          + "   seam/med %5.2f" % (ac[i][0] / max(amed, 1e-9)))

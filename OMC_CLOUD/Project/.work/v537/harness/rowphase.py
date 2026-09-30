#!/usr/bin/env python3
"""rowphase.py SRC DEC W H NFRAMES [--fmt][--depth][--sh 16] [--label X]

DETAIL RETENTION AS A FUNCTION OF ROW POSITION INSIDE THE SLICE.

The single most decisive measurement in the flattening investigation, and it is
one line of statistics rather than a map: for every picture row, the ratio of
the decode's horizontal gradient energy to the source's, then averaged over all
rows with the same (row mod slice_h).

If a codec's sharpness does not depend on where a row falls inside its coding
unit, every phase reads the same and the profile is flat.  Any structure here
is the coding grid printing itself onto the picture -- which is BOTH a
flattening defect (the interior is softer than it should be) AND a horizontal
line defect (the boundary is sharper than its neighbours, so the eye sees an
edge at a fixed pitch).  The same profile is therefore the instrument for both.

Also reports the CHROMA profile, because a luma-only reading of this would have
missed that the two planes do not have the same profile.
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
lab   = a[a.index('--label')+1]      if '--label' in a else dec

def gx(p):
    return np.abs(np.diff(p, axis=1)).mean(axis=1)

accS = np.zeros((3, sh)); accD = np.zeros((3, sh)); cnt = np.zeros(sh)
for f in range(N):
    sy, scb, scr = yuvio.planes(src, W, H, f, fmt, depth)
    dy, dcb, dcr = yuvio.planes(dec, W, H, f, fmt, depth)
    for i, (sp, dp) in enumerate(((sy, dy), (scb, dcb), (scr, dcr))):
        s_, d_ = gx(sp), gx(dp)
        for r in range(H):
            accS[i, r % sh] += s_[r]; accD[i, r % sh] += d_[r]
    for r in range(H):
        cnt[r % sh] += 1

print("%s   detail retention by row phase inside the %d-row slice" % (lab, sh))
print("  phase:  " + " ".join("%6d" % p for p in range(sh)))
for i, nm in enumerate(("Y ", "Cb", "Cr")):
    rat = accD[i] / np.maximum(accS[i], 1e-9)
    print("  %s ret: " % nm + " ".join("%6.3f" % v for v in rat))
    print("  %s dev: " % nm + " ".join("%+6.1f" % (100.0*(v/rat.mean()-1)) for v in rat)
          + "   %%  (spread %.1f%% of mean)" % (100.0*(rat.max()-rat.min())/rat.mean()))

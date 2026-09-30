#!/usr/bin/env python3
"""fidelity.py SRC DEC W H NFRAMES [--fmt][--depth][--label X][--hp 1]

DOES THE DETAIL THAT SURVIVED ACTUALLY MATCH THE SOURCE'S DETAIL?

h/armscore.py's `ret` column measures how MUCH high-frequency energy the decode
carries relative to the source.  It cannot tell restored detail from INVENTED
detail, and that distinction decides whether a candidate fix is a fix at all:

  * the codec's own grain fill raises luma retention 0.596 -> 0.830 and chroma
    0.288 -> 0.750, which looks like a spectacular repair;
  * the codec's own source comment records that at the finest luma band it
    "retains 3.5x JPEG XS's energy but only a third of its correlation with the
    source (0.059 vs 0.161), i.e. the texture is plausible but not the
    source's."

So retention alone would have shipped invented grain as a detail fix.  This
measures the other half: the Pearson correlation, per plane, between the
decode's high-pass residual and the source's, over the whole frame.

  rho = 1.0   every surviving detail sample is the source's own
  rho = 0.0   the decode's texture is uncorrelated with the source's --
              plausible noise, credited by no honest metric

Read the two together.  A real improvement raises retention AND holds or raises
rho.  Anything that raises retention while dropping rho is fill by another name.
All three planes, always.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio

a = sys.argv
src, dec, W, H, N = a[1], a[2], int(a[3]), int(a[4]), int(a[5])
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
lab   = a[a.index('--label')+1]      if '--label' in a else os.path.basename(dec)

def hp(p):
    """High-pass = the plane minus its own 3x3 box mean.  A box filter, not a
    Gaussian: integer, separable, and the cheapest thing that is honest here."""
    q = np.pad(p, 1, mode='edge')
    box = (q[:-2, :-2] + q[:-2, 1:-1] + q[:-2, 2:] +
           q[1:-1, :-2] + q[1:-1, 1:-1] + q[1:-1, 2:] +
           q[2:, :-2] + q[2:, 1:-1] + q[2:, 2:]) / 9.0
    return p - box

num = np.zeros(3); ds = np.zeros(3); dd = np.zeros(3); en_s = np.zeros(3); en_d = np.zeros(3)
for f in range(N):
    S = yuvio.planes(src, W, H, f, fmt, depth)
    D = yuvio.planes(dec, W, H, f, fmt, depth)
    for i in range(3):
        u, v = hp(S[i]), hp(D[i])
        u = u - u.mean(); v = v - v.mean()
        num[i] += float((u * v).sum()); ds[i] += float((u * u).sum()); dd[i] += float((v * v).sum())
        en_s[i] += float(np.abs(hp(S[i])).sum()); en_d[i] += float(np.abs(hp(D[i])).sum())
rho = num / np.maximum(np.sqrt(ds * dd), 1e-9)
ret = en_d / np.maximum(en_s, 1e-9)
# "true detail" -- the part of the source's high-pass energy the decode actually
# reproduces, i.e. retention discounted by how much of it is the right texture.
true = rho * np.sqrt(np.maximum(ret, 0))
print("%-26s rho Y/Cb/Cr %.4f/%.4f/%.4f   hpret %.3f/%.3f/%.3f   TRUEDETAIL %.3f/%.3f/%.3f"
      % (lab, rho[0], rho[1], rho[2], ret[0], ret[1], ret[2], true[0], true[1], true[2]))

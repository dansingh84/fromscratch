#!/usr/bin/env python3
"""rowfid.py SRC DEC W H NFRAMES [--fmt][--depth][--sh 16][--label X]

ROW-PHASE FIDELITY -- the decisive form of h/rowphase.py.

rowphase.py reports detail RETENTION by row position inside the slice, and
found a large structure: OMC's luma retention swings 19.5% of its mean across
the sixteen phases where JPEG XS's swings 5.5%, and its chroma swings 61-64%
where XS swings 22-35%.

Retention alone cannot say what that structure MEANS.  A phase can carry more
energy because it kept more of the source's detail, or because it is ringing.
Those need opposite fixes.  So this reports, per row phase and per plane:

  ret   the same energy retention, for continuity with rowphase.py
  rho   the CORRELATION of the decode's high-pass with the source's, computed
        on that phase's rows only

  ret high + rho high  -> that phase really is better served: an ALLOCATION
                          imbalance, and the fix is to level it at constant
                          rate, which costs no bits
  ret high + rho low   -> that phase is RINGING: extra energy that is not the
                          source's, and levelling it would be the wrong fix

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
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
lab   = a[a.index('--label')+1]      if '--label' in a else os.path.basename(dec)

def hp(p):
    q = np.pad(p, 1, mode='edge')
    box = (q[:-2,:-2]+q[:-2,1:-1]+q[:-2,2:]+q[1:-1,:-2]+q[1:-1,1:-1]+q[1:-1,2:]
           + q[2:,:-2]+q[2:,1:-1]+q[2:,2:]) / 9.0
    return p - box

num = np.zeros((3, sh)); su = np.zeros((3, sh)); sv = np.zeros((3, sh))
es = np.zeros((3, sh)); ed = np.zeros((3, sh))
for f in range(N):
    S = yuvio.planes(src, W, H, f, fmt, depth)
    D = yuvio.planes(dec, W, H, f, fmt, depth)
    for i in range(3):
        u, v = hp(S[i]), hp(D[i])
        for ph in range(sh):
            uu = u[ph::sh]; vv = v[ph::sh]
            uu = uu - uu.mean(); vv = vv - vv.mean()
            num[i, ph] += float((uu*vv).sum()); su[i, ph] += float((uu*uu).sum())
            sv[i, ph] += float((vv*vv).sum())
            es[i, ph] += float(np.abs(u[ph::sh]).sum()); ed[i, ph] += float(np.abs(v[ph::sh]).sum())
rho = num / np.maximum(np.sqrt(su*sv), 1e-9)
ret = ed / np.maximum(es, 1e-9)
print("%s   row phase inside the %d-row slice" % (lab, sh))
print("   phase:" + "".join("%7d" % p for p in range(sh)))
for i, nm in enumerate(("Y ", "Cb", "Cr")):
    print("   %s ret:" % nm + "".join("%7.3f" % v for v in ret[i])
          + "   spread %5.1f%%" % (100.0*(ret[i].max()-ret[i].min())/ret[i].mean()))
    print("   %s rho:" % nm + "".join("%7.3f" % v for v in rho[i])
          + "   spread %5.1f%%" % (100.0*(rho[i].max()-rho[i].min())/rho[i].mean()))

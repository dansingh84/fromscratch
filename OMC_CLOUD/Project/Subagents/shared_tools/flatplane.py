#!/usr/bin/env python3
"""flatplane.py - per-plane flatness, so 'no flatness' can be asserted for Y, Cb and Cr
separately rather than for a combined energy in which one plane can hide inside another.

flatpatch.py measures  hp(Y) + 0.5*(hp(Cb) + hp(Cr))  as a single number.  A block whose
CHROMA has been flattened while its LUMA still carries texture does not cross that combined
threshold and is never flagged.  Constraint C5 says never measure luma only; measuring a
luma-dominated MIXTURE is the same trap with an extra step.

Same rule as flatpatch, applied one plane at a time, and the reference is always the SOURCE:
    flat  <=>  decode block energy < thr * median(source energy)
               AND source block energy > 0.5 * median(source energy)

  flatplane.py <src.yuv> <dec.yuv> <W> <H> <frame> [--fmt 422] [--depth 10] [--blk 16] [--thr 0.35]
"""
import sys
import numpy as np
import yuvio

a = sys.argv[1:]
src, dec, W, H, F = a[0], a[1], int(a[2]), int(a[3]), int(a[4])
fmt, depth, blk, thr = '422', 10, 16, 0.35
i = 5
while i < len(a):
    if   a[i] == '--fmt':   fmt = a[i+1];        i += 2
    elif a[i] == '--depth': depth = int(a[i+1]); i += 2
    elif a[i] == '--blk':   blk = int(a[i+1]);   i += 2
    elif a[i] == '--thr':   thr = float(a[i+1]); i += 2
    else: i += 1

def hp(p):
    q = np.pad(p, 1, mode='edge')
    box = (q[:-2,:-2]+q[:-2,1:-1]+q[:-2,2:]+q[1:-1,:-2]+q[1:-1,1:-1]+q[1:-1,2:]
           + q[2:,:-2]+q[2:,1:-1]+q[2:,2:]) / 9.0
    return np.abs(p - box)

def bl(x, b):
    nh, nw = x.shape[0]//b, x.shape[1]//b
    return x[:nh*b, :nw*b].reshape(nh, b, nw, b).mean(axis=(1,3))

ys, cbs, crs = yuvio.planes(src, W, H, F, fmt, depth)
yd, cbd, crd = yuvio.planes(dec, W, H, F, fmt, depth)

out = []
for name, ps, pd in (('Y', ys, yd), ('Cb', cbs, cbd), ('Cr', crs, crd)):
    es, ed = bl(hp(ps.astype(np.float64)), blk), bl(hp(pd.astype(np.float64)), blk)
    med = float(np.median(es))
    if med <= 0:
        out.append("%s   n/a (source median 0)" % name); continue
    textured = es > 0.5*med
    flat = (ed < thr*med) & textured
    pct = 100.0*flat.sum()/max(int(textured.sum()), 1)
    out.append("%-3s %6.2f%% of %d textured blocks" % (name, pct, int(textured.sum())))

print("   " + " | ".join(out))

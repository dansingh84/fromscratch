#!/usr/bin/env python3
"""per-plane PSNR of one slice. usage: slice_psnr.py src dec W H fmt(422|444|420) depth frame slice sh"""
import sys, numpy as np, math
src, dec, W, H, fmt, D, f, s, sh = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:5]), sys.argv[5], *map(int, sys.argv[6:10])
cw, ch = {'422': (W // 2, H), '444': (W, H), '420': (W // 2, H // 2)}[fmt]
fs = W * H + 2 * cw * ch
def plane(path, p):
    a = np.memmap(path, dtype='<u2', mode='r')
    base = f * fs
    if p == 0: return np.asarray(a[base:base + W * H]).reshape(H, W).astype(np.int64)
    o = base + W * H + (p - 1) * cw * ch
    return np.asarray(a[o:o + cw * ch]).reshape(ch, cw).astype(np.int64)
peak = (1 << D) - 1; out = []
for p in range(3):
    A, B = plane(src, p), plane(dec, p)
    rsh = sh if (p == 0 or fmt != '420') else sh // 2
    r0, r1 = s * rsh, min((s + 1) * rsh, A.shape[0])
    d = (A[r0:r1] - B[r0:r1]) ** 2; m = d.mean()
    out.append(99.0 if m == 0 else 10 * math.log10(peak * peak / m))
print('PSNR %.4f %.4f %.4f' % tuple(out))

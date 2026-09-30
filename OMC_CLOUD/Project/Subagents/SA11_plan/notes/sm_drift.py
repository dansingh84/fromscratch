#!/usr/bin/env python3
"""[SA11 SM] per-plane PSNR (steady frames) and row-phase mean SIGNED error within the slice (level drift).
usage: sm_drift.py SRC DEC W H sh f0 f1"""
import sys, numpy as np, math
src, dec, W, H, sh, f0, f1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), int(sys.argv[7])
cw = W // 2; fs = W * H + 2 * cw * H
acc = [np.zeros(sh), np.zeros(sh), np.zeros(sh)]; cnt = [np.zeros(sh)] * 3; mse = [0.0] * 3; n = 0
ph = [[], [], []]
for f in range(f0, f1 + 1):
    a = np.fromfile(src, dtype='<u2', count=fs, offset=f * fs * 2).astype(float)
    b = np.fromfile(dec, dtype='<u2', count=fs, offset=f * fs * 2).astype(float)
    for k, (o, w) in enumerate(((0, W), (W * H, cw), (W * H + cw * H, cw))):
        e = (b[o:o + w * H] - a[o:o + w * H]).reshape(H, w)
        mse[k] += float((e ** 2).mean())
        Hs = (H // sh) * sh
        ph[k].append(e[:Hs].reshape(-1, sh, w).mean(axis=(0, 2)))
    n += 1
print('steady frames %d-%d  PSNR Y/Cb/Cr %s' % (f0, f1, '/'.join('%.2f' % (10 * math.log10(1023 ** 2 / (m / n))) for m in mse)))
for k, nm in enumerate('YBR'):
    p = np.mean(ph[k], 0)
    print('  %s row-phase mean SIGNED error (codes): %s   (last - first row %+.2f)' % (nm, ' '.join('%+.2f' % v for v in p), p[-1] - p[0]))

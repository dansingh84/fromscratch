#!/usr/bin/env python3
# diag_bands.py CLIP R: error energy per scale band, ours (form-(i) PO intra at the step whose S16 bpp ~ R, from the
# fit/lane log) vs today's frame 0 at R. Band k = boxavg_2^k(e) - boxavg_2^(k+1)(e), e = decode - source, luma + chroma.
import sys, os, re, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read
from n4_core import po
W, H = 1280, 720; ROOT = '/home/user/fromscratch/OMC_CLOUD/'
CLIP, R, LOG = sys.argv[1], float(sys.argv[2]), sys.argv[3]
pts = [(float(m.group(2)), float(m.group(1))) for m in (re.match(r'\S+ \S+ Q=(\S+) bpp (\S+)', l) for l in open(LOG)) if m]
Q = min(pts, key=lambda p: abs(np.log2(p[0] / R)))[1]
x = read(ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % CLIP, W, H, 0)
ours = [po(p, Q, 0.7, 0, [])[1] for p in x]
t = read(ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (CLIP, sys.argv[2]), W, H, 0)
def box(e, k):
    if k == 0: return e.astype(float)
    b = 2 ** k; h, w = (e.shape[0] // b) * b, (e.shape[1] // b) * b
    m = e[:h, :w].astype(float).reshape(h // b, b, w // b, b).mean(axis=(1, 3))
    return np.repeat(np.repeat(m, b, 0), b, 1)
def bands(e):
    h, w = (e.shape[0] // 32) * 32, (e.shape[1] // 32) * 32; e = e[:h, :w]
    return [((box(e, k) - box(e, k + 1)) ** 2).mean() for k in range(5)] + [(box(e, 5) ** 2).mean()]
print('%s @%.1f ours Q=%.2f' % (CLIP, R, Q))
for k, nm in enumerate('Y Cb Cr'.split()):
    bo = bands(ours[k] - x[k]); bt = bands(t[k] - x[k])
    print('  %s band energy ours/today (fine -> coarse, last = DC>32px): ' % nm + ' '.join('%.2f' % (a / max(b, 1e-9)) for a, b in zip(bo, bt)),
          '| abs ours ' + ' '.join('%.1f' % a for a in bo))

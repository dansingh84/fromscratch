#!/usr/bin/env python3
# make_synth.py — rebuilds the synthetic clips exactly as used in the SA20 log (DESIGN.md "Clips"), all derived from
# frame 0 of the owner's cine_A005C031 (720p 4:2:2 10-bit, as converted by conv.sh). Order and seed matter: the
# noisy clips draw from ONE generator seeded 7, sigma 1, 2, 3 first, then the noisy pan.
import sys, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bench'))
from d1_screen import read
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
x = read(A + 'cine_A005C031_1280x720_422_10.yuv', 1280, 720, 0)
def put(fn, frames):
    with open(A + fn, 'wb') as f:
        for fr in frames:
            for p in fr: p.astype('<u2').tofile(f)
put('cine_frozen_1280x720_422_10.yuv', [x] * 3)           # byte-identical frame 0 x 3
put('cine_frozen10_1280x720_422_10.yuv', [x] * 10)
def lanczos_shift(p, d, a=3):
    n = np.arange(-a + 1, a + 1); fr = d - np.floor(d); w = np.sinc(n - fr) * np.sinc((n - fr) / a); w /= w.sum()
    ip = int(np.floor(d)); off = a + abs(ip) + 2; pp = np.pad(p.astype(float), ((0, 0), (off, off)), mode='edge'); o = np.zeros(p.shape)
    for k, wk in zip(n, w): o += wk * pp[:, off - ip - k: off - ip - k + p.shape[1]]
    return np.clip(np.round(o), 0, 1023).astype('<u2')
for v in (0.25, 0.5, 1.0):   # horizontal pans, chroma shifted by half (4:2:2)
    put('cine_pan%s_1280x720_422_10.yuv' % v, [[lanczos_shift(p, v * t if k == 0 else v * t / 2) for k, p in enumerate(x)] for t in range(10)])
rng = np.random.default_rng(7)
for sg in (1, 2, 3):
    put('cine_nfrozen%d_1280x720_422_10.yuv' % sg, [[np.clip(np.round(p + rng.normal(0, sg, p.shape)), 0, 1023) for p in x] for t in range(10)])
fs = 1280 * 720 * 2
with open(A + 'cine_pan0.5_1280x720_422_10.yuv', 'rb') as f, open(A + 'cine_npan0.5s2_1280x720_422_10.yuv', 'wb') as g:
    for t in range(10):
        fr = np.frombuffer(f.read(fs * 2), '<u2').astype(float)
        np.clip(np.round(fr + rng.normal(0, 2, fr.shape)), 0, 1023).astype('<u2').tofile(g)
print('synthetic clips written to', A)

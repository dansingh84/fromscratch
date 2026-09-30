#!/usr/bin/env python3
"""Pixel-for-pixel difference render (owner instruction 2026-09-02): |decode - source| per plane,
amplified, plus the per-row mean error profile (seams show as spikes at the slice pitch).
usage: eye_diff.py src.yuv dec.yuv W H frame out.png [--fmt 422] [--depth 10] [--gain 8] [--sh 8]
"""
import sys, numpy as np
from PIL import Image
a = sys.argv[1:]; fmt, depth, gain, sh = '422', 10, 8, 0
for k, cast in (('--fmt', str), ('--depth', int), ('--gain', int), ('--sh', int)):
    if k in a: i = a.index(k); v = cast(a[i+1]); del a[i:i+2]; fmt, depth, gain, sh = (v if k=='--fmt' else fmt), (v if k=='--depth' else depth), (v if k=='--gain' else gain), (v if k=='--sh' else sh)
src, dec, W, H, f, out = a[0], a[1], int(a[2]), int(a[3]), int(a[4]), a[5]
Wc = W // 2 if fmt == '422' else W; fw = W*H + 2*Wc*H; mx = (1 << depth) - 1
def planes(p):
    d = np.fromfile(p, dtype=np.uint16)[f*fw:(f+1)*fw].astype(np.int32)
    return d[:W*H].reshape(H, W), d[W*H:W*H+Wc*H].reshape(H, Wc), d[W*H+Wc*H:].reshape(H, Wc)
sy, scb, scr = planes(src); dy, dcb, dcr = planes(dec)
dY, dCb, dCr = np.abs(dy - sy), np.abs(dcb - scb), np.abs(dcr - scr)
sc = 255.0 / mx * gain
def up(c): return np.repeat(c, 2, axis=1)[:, :W] if Wc != W else c
rgb = np.stack([np.clip(dY*sc, 0, 255), np.clip(up(dCb)*sc, 0, 255), np.clip(up(dCr)*sc, 0, 255)], -1).astype(np.uint8)
# row profile strip (right side, 160 px wide): mean |dY| per row
prof = dY.mean(axis=1); pm = prof.max() if prof.max() > 0 else 1
strip = np.zeros((H, 160, 3), np.uint8)
for r in range(H):
    n = int(prof[r] / pm * 150); strip[r, :n, :] = [255, 255, 255]
    if sh and r % sh == 0: strip[r, 150:160, :] = [255, 0, 0]
Image.fromarray(np.concatenate([rgb, strip], axis=1)).save(out)
rows = np.argsort(prof)[::-1][:12]
print(out, 'mean|dY| %.2f max %d; worst rows:' % (prof.mean(), int(dY.max())), ' '.join('%d(%.1f)' % (r, prof[r]) for r in sorted(rows)))
if sh:
    onb = prof[[r for r in range(H) if r % sh in (0, sh-1)]].mean(); inb = prof[[r for r in range(H) if r % sh not in (0, sh-1)]].mean()
    print('  boundary rows mean %.2f vs interior rows mean %.2f (ratio %.2f)' % (onb, inb, onb / inb if inb else 0))

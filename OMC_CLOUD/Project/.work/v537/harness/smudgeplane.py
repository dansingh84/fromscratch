#!/usr/bin/env python3
"""smudgeplane.py SRC.yuv DEC.yuv W H FRAME [--fmt 422] [--depth 10] [--sh 16] [--ratio 0.70]

PER-PLANE detail loss.  A SMUDGE leaves a block's MEAN alone and removes its TEXTURE: the
local standard deviation collapses while the mean stays put, so a level metric reads the
block as clean while the picture visibly loses detail.

h/smudge.py measures exactly this but reads `[:W*H]` -- the Y plane ONLY.  Chroma smudging
has therefore never been measured in this project.  That is constraint C5's trap, the same
one h/flatpatch.py fell into with its combined Y + 0.5(Cb+Cr) energy, and it is why this
file exists.

Per (slice_h/4) x 32 block, report the share of TEXTURED blocks (source sd >= 8 codes,
scaled to the coded depth) whose sd(decode)/sd(source) falls below --ratio.  A flat block
cannot be smudged, so untextured blocks are excluded from the denominator -- the same
discipline h/flatplane.py uses.
"""
import sys
import numpy as np

a = sys.argv
src, dec, W, H, f = a[1], a[2], int(a[3]), int(a[4]), int(a[5])
fmt   = a[a.index('--fmt')+1]          if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1])   if '--depth' in a else 10
sh    = int(a[a.index('--sh')+1])      if '--sh'    in a else 16
RAT   = float(a[a.index('--ratio')+1]) if '--ratio' in a else 0.70
SDMIN = 8.0 * (1 << depth) / 1024.0

CW = W // 2 if fmt == '422' else W
per = W*H + 2*CW*H                      # samples per frame, all three planes

def planes(path):
    d = np.fromfile(path, dtype='<u2', count=per, offset=f*per*2).astype(float)
    y  = d[:W*H].reshape(H, W)
    cb = d[W*H:W*H+CW*H].reshape(H, CW)
    cr = d[W*H+CW*H:].reshape(H, CW)
    return y, cb, cr

ys, cbs, crs = planes(src)
yd, cbd, crd = planes(dec)

bh = sh // 4
out = []
for name, s, d in (('Y', ys, yd), ('Cb', cbs, cbd), ('Cr', crs, crd)):
    hh, ww = s.shape
    bw = 32 if ww >= 32 else max(ww, 1)
    nh, nw = hh // bh, ww // bw
    if nh == 0 or nw == 0:
        out.append("%-3s n/a" % name); continue
    def blk(x):
        return x[:nh*bh, :nw*bw].reshape(nh, bh, nw, bw)
    sd_s = blk(s).std(axis=(1, 3))
    sd_d = blk(d).std(axis=(1, 3))
    textured = sd_s >= SDMIN
    if not textured.any():
        out.append("%-3s n/a (no textured block)" % name); continue
    ratio = np.where(textured, sd_d / np.maximum(sd_s, 1e-6), 1.0)
    smudged = (ratio < RAT) & textured
    pct = 100.0 * smudged.sum() / textured.sum()
    out.append("%-3s %6.2f%% of %d textured blocks (mean sd ratio %.3f)"
               % (name, pct, int(textured.sum()), float(ratio[textured].mean())))

print("   " + " | ".join(out))

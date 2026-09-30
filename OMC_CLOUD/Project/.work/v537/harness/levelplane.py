#!/usr/bin/env python3
"""levelplane.py SRC.yuv DEC.yuv W H NFRAMES [--fmt 422] [--depth 10] [--sh 16] [--thr 20]

PER-PLANE LEVEL ERROR -- the owner's "smudge": a region whose BRIGHTNESS is wrong.
Bright places going dark, dark places going darker, bright places going brighter.

VOCABULARY, because the harness and the owner disagree and it has caused real confusion:
  owner "smudge"     = a LEVEL shift over a coherent region   -> THIS FILE (and blotch/wash/levelmap)
  owner "flat block" = a patch of ZERO DETAIL                 -> h/flatplane.py
h/smudge.py is named for the second but its own docstring defines it as texture loss, i.e. it
measures FLATNESS, not the owner's smudge. Do not use it to answer a smudge question.

blotch.py, levelmap.py and washmap.py all quantify the level error correctly -- and all three
read `[:W*H]`, the Y plane ONLY. Chroma level error has therefore never been measured in this
project, though sect.50.1 item 4 is a CHROMA observation. That is why this file exists.

Per LL-support block ((slice_h/4) rows x 32 columns) take the MEAN SIGNED error, which is zero
for quantisation noise and non-zero only when a level is genuinely wrong. Report, per plane, over
all frames: the worst |mean|, the 99.9th percentile, and the count of blocks past --thr codes.
All figures are scaled to a 10-bit code scale so depths compare directly.
"""
import sys
import numpy as np

a = sys.argv
src, dec, W, H, NF = a[1], a[2], int(a[3]), int(a[4]), int(a[5])
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
THR   = float(a[a.index('--thr')+1]) if '--thr'   in a else 20.0

CW  = W // 2 if fmt == '422' else W
per = W*H + 2*CW*H
SCALE = 1024.0 / (1 << depth)          # report on the 10-bit scale
bh = sh // 4

def planes(path, f):
    d = np.fromfile(path, dtype='<u2', count=per, offset=f*per*2).astype(np.float64)
    return (d[:W*H].reshape(H, W),
            d[W*H:W*H+CW*H].reshape(H, CW),
            d[W*H+CW*H:].reshape(H, CW))

acc = {n: [] for n in ('Y', 'Cb', 'Cr')}
for f in range(NF):
    S = planes(src, f); D = planes(dec, f)
    for name, s, d in zip(('Y', 'Cb', 'Cr'), S, D):
        hh, ww = s.shape
        bw = 32 if ww >= 32 else max(ww, 1)
        nh, nw = hh // bh, ww // bw
        if nh == 0 or nw == 0:
            continue
        e = (d - s) * SCALE
        m = e[:nh*bh, :nw*bw].reshape(nh, bh, nw, bw).mean(axis=(1, 3))
        acc[name].append(m.ravel())

out = []
for name in ('Y', 'Cb', 'Cr'):
    if not acc[name]:
        out.append("%-3s n/a" % name); continue
    v = np.abs(np.concatenate(acc[name]))
    out.append("%-3s worst %6.1f  p99.9 %5.1f  blocks>%.0f: %d"
               % (name, v.max(), np.percentile(v, 99.9), THR, int((v > THR).sum())))
print("   " + "\n   ".join(out))

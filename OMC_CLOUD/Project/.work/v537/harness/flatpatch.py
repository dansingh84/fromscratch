#!/usr/bin/env python3
"""flatpatch.py SRC DEC W H FRAME OUT.png [--fmt][--depth][--blk 8][--sh 16]
               [--label X] [--thr 0.35]

HIGHLIGHT THE FLAT PATCHES -- exactly what the owner asked for on 2026-08-26:
"if you were to visually highlight flat detail areas in the image, they would
appear."

This is NOT h/flat15.py.  That measures how much detail was lost RELATIVE to
what the rate explains, which is the right question for ranking two arms and the
wrong question for finding a patch a viewer can point at.  A viewer does not see
a ratio; a viewer sees a REGION THAT HAS NO TEXTURE sitting next to a region
that does.  So this asks the viewer's question:

    is this block's texture far below the texture of the blocks AROUND IT,
    in the DECODE, in a place where the SOURCE had texture?

Two conditions, both required:

  1. the block's own high-frequency energy is below `thr` times the frame's
     median -- it is flat in absolute terms, not merely reduced;
  2. the SOURCE had real texture there -- so a genuinely flat wall is never
     flagged, however flat the decode renders it.

Both luma and chroma contribute, because a patch that keeps its luma texture and
loses its colour texture reads as flat too.

The map is rendered so a flat patch is BRIGHT MAGENTA over a dimmed copy of the
decode, which puts the finding and its context in one picture -- a bare mask
cannot be checked against the image by eye, and every detector in this project
that could not be checked by eye was eventually wrong.

It also reports the SLICE ALIGNMENT of what it flags, because a flat patch that
lands on slice boundaries is a coding-granularity defect with a specific cause,
and one that does not is a rate effect.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio

a = sys.argv
src, dec, W, H, F, out = a[1], a[2], int(a[3]), int(a[4]), int(a[5]), a[6]
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
blk   = int(a[a.index('--blk')+1])   if '--blk'   in a else 8
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
lab   = a[a.index('--label')+1]      if '--label' in a else os.path.basename(dec)
thr   = float(a[a.index('--thr')+1]) if '--thr'   in a else 0.35

def hp(p):
    q = np.pad(p, 1, mode='edge')
    box = (q[:-2,:-2]+q[:-2,1:-1]+q[:-2,2:]+q[1:-1,:-2]+q[1:-1,1:-1]+q[1:-1,2:]
           + q[2:,:-2]+q[2:,1:-1]+q[2:,2:]) / 9.0
    return np.abs(p - box)

def blocks(x, b):
    nh, nw = x.shape[0]//b, x.shape[1]//b
    return x[:nh*b, :nw*b].reshape(nh, b, nw, b).mean(axis=(1,3))

def energy(path, f):
    y, cb, cr = yuvio.planes(path, W, H, f, fmt, depth)
    cbf, crf = yuvio.upchroma(cb, W, fmt), yuvio.upchroma(cr, W, fmt)
    return blocks(hp(y), blk) + 0.5*(blocks(hp(cbf), blk) + blocks(hp(crf), blk))

es, ed = energy(src, F), energy(dec, F)
med_s = float(np.median(es))
# THE REFERENCE IS THE SOURCE, NEVER THE DECODE.
#
# The first version of this script compared each block against the DECODE's own
# median.  That is a moving reference: switch grain fill on and the median
# rises, so blocks that did not change at all fall further below it and get
# flagged.  It ranked a fill sweep exactly backwards -- more fill "produced"
# more flat patches -- which is a property of the yardstick, not of the picture.
# Normalising against the SOURCE's median makes "flat" mean "flat compared with
# what the master actually has here", which is the same yardstick for every arm.
flat = (ed < thr*med_s) & (es > 0.5*med_s)     # flat in the decode, textured in the source
nh, nw = flat.shape

# ---- slice alignment of what was flagged
rows = np.repeat(np.arange(nh)*blk, nw).reshape(nh, nw)
prof = np.zeros(sh); tot = np.zeros(sh)
for ph in range(sh):
    m = (rows % sh) == ph
    if m.sum():
        prof[ph] = float(flat[m].mean()); tot[ph] = float(m.sum())
med = float(np.median(prof))
print("%-30s flat patches %6d of %6d blocks (%5.2f%%)  slice-phase peak/median %.2f"
      % (lab, int(flat.sum()), flat.size, 100.0*flat.mean(),
         (prof.max()/max(med,1e-9)) if med > 0 else float('inf')))
print("   by slice phase:" + "".join("%6.2f" % (100.0*v) for v in prof))

# ---- runs of ENTIRE flat slice rows: the signature of a per-slice decision
rowfrac = flat.mean(axis=1)
srow = np.zeros(H//sh)
for s_ in range(H//sh):
    lo, hi = s_*sh//blk, min((s_+1)*sh//blk, nh)
    if hi > lo: srow[s_] = float(rowfrac[lo:hi].mean())
hot = int((srow > 0.25).sum())
print("   whole SLICE ROWS more than 25%% flat: %d of %d (%.1f%%)"
      % (hot, len(srow), 100.0*hot/max(len(srow),1)))

# ---- render: magenta over a dimmed decode
from PIL import Image
y, cb, cr = yuvio.planes(dec, W, H, F, fmt, depth)
cbf, crf = yuvio.upchroma(cb, W, fmt), yuvio.upchroma(cr, W, fmt)
mid = 1 << (depth-1)
r = y + 1.5748*(crf-mid); g = y - 0.1873*(cbf-mid) - 0.4681*(crf-mid); b = y + 1.8556*(cbf-mid)
img = np.stack([r, g, b], -1)
img = np.clip(img / float((1 << depth) - 1), 0, 1) ** (1/2.2)
img = (img * 110).astype(np.uint8)                    # dim the context
big = np.repeat(np.repeat(flat, blk, 0), blk, 1)
img = img[:big.shape[0], :big.shape[1]]
img[big, 0] = 255; img[big, 1] = 0; img[big, 2] = 220
Image.fromarray(img).save(out)
print("   -> %s" % out)

#!/usr/bin/env python3
"""xrow.py SRC.yuv DEC.yuv W H NFRAMES [--fmt 422] [--depth 10] [--sh 16]
          [--label NAME]

CROSS-CODEC form of sect.51's wash instrument.

`h/fpscore.py` measures the repair FOOTPRINT: |DEC - REF| where REF is the same
cell with OMC's in-gamut repair disabled.  That is the sharpest attribution
available for OMC, but it is defined against an OMC arm and therefore has no
analogue in another codec.  Every other property of the artifact is a property
of the decoded picture against the source, so it can be measured on ANY decoder
output at any rate.  This script reports exactly those, so that JPEG XS at
1.0 bpp can be placed in the same table as OMC at 0.5 bpp -- the comparison the
project goal names (parity with XS gen 1 at half its bitrate).

Rows, all on a common 10-bit code scale:

  worst block      max over frames and 4x32 LL-support blocks of |mean signed
                   error|.  The defining property of the artifact.
  n>20 / n>40      how many such blocks are past 20 / 40 codes, over the clip.
  wash flicker     the per-frame mean of |block level| has a standard deviation
                   and a largest frame-to-frame step.  The owner's requirement
                   (2026-08-25): "any change in prevalence of these errors
                   between frames will appear as flicker, which we don't want."
                   A codec can hold a low mean and still flicker; this catches
                   that.
  sat fraction     fraction of luma samples with |error| >= 40 codes, i.e. the
                   pixels the sect.50.7 error map renders at full saturation.
  |err| mean       mean |DEC - SRC| over luma, and its own per-frame sd/step.
                   Source-referenced, so it is NOT the repair footprint: it
                   includes ordinary quantisation noise, which at 0.5 bpp is
                   large and legitimate.  Listed for completeness only.

Lower is better on every row EXCEPT that `|err| mean` is not comparable across
different bitrates and must not be read as a quality ranking.
"""
import sys, numpy as np
a = sys.argv
src, dec, W, H, N = a[1], a[2], int(a[3]), int(a[4]), int(a[5])
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
label = a[a.index('--label')+1]      if '--label' in a else dec
per = W*H*2 if fmt == '422' else W*H*3
k   = 1024.0/(1 << depth)
bh, bw = sh//4, 32
nh, nw = H//bh, W//bw
worst = 0.0; n20 = 0; n40 = 0
lvl_pf = []; err_pf = []; sat_pf = []
for f in range(N):
    s = np.fromfile(src, dtype='<u2', count=per, offset=f*per*2)[:W*H].reshape(H, W).astype(np.float64)
    d = np.fromfile(dec, dtype='<u2', count=per, offset=f*per*2)[:W*H].reshape(H, W).astype(np.float64)
    e = (d - s) * k
    blk = e[:nh*bh, :nw*bw].reshape(nh, bh, nw, bw).mean(axis=(1, 3))
    ab  = np.abs(blk)
    worst = max(worst, float(ab.max()))
    n20 += int((ab > 20).sum()); n40 += int((ab > 40).sum())
    lvl_pf.append(float(ab.mean()))
    err_pf.append(float(np.abs(e).mean()))
    sat_pf.append(float((np.abs(e) >= 40).mean()))
def sd_step(v):
    v = np.array(v)
    return float(v.mean()), float(v.std()), (float(np.abs(np.diff(v)).max()) if len(v) > 1 else 0.0)
lm, ls, lt = sd_step(lvl_pf); em, es, et = sd_step(err_pf); sm, ss, st = sd_step(sat_pf)
print("%-22s worst %6.1f  n>20 %5d  n>40 %5d  | wash mean %6.3f sd %6.3f step %6.3f"
      "  | sat %.4f sd %.4f step %.4f  | |err| %6.3f sd %.3f step %.3f"
      % (label, worst, n20, n40, lm, ls, lt, sm, ss, st, em, es, et))

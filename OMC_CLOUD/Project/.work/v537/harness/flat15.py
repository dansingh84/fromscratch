#!/usr/bin/env python3
"""flat15.py SRC.yuv DEC.yuv W H FRAME OUTDIR [--fmt 422] [--depth 10]
            [--blk 8] [--tag NAME] [--maps 0|1]

Runs all fifteen flattening measures of h/flatlib.py on one frame and writes
one full-frame map per measure plus a CONSENSUS map.  Prints a one-line
summary per measure so two arms can be compared without opening a file.

The CONSENSUS map is the point of running fifteen: it is the count, per block,
of how many INDEPENDENT measures call that block flattened (ratio < 0.70).
A block that ten different statistics all call flat is flat.  A block that one
calls flat is that statistic's blind spot showing.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio, flatlib

a = sys.argv
src, dec, W, H, F, outdir = a[1], a[2], int(a[3]), int(a[4]), int(a[5]), a[6]
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
blk   = int(a[a.index('--blk')+1])   if '--blk'   in a else 8
tag   = a[a.index('--tag')+1]        if '--tag'   in a else 'arm'
maps  = int(a[a.index('--maps')+1])  if '--maps'  in a else 1
norm  = int(a[a.index('--norm')+1])  if '--norm'  in a else 1   # rate-normalise (see flatlib.normalise)
ref   = a[a.index('--ref')+1]        if '--ref'   in a else None
# --ref REF.yuv switches the whole run into DIFFERENTIAL mode: every measure is
# computed for DEC and for REF against the SAME source and the map is their
# ratio, so 1.0 means "this codec kept exactly as much detail here as the
# reference did" and below 1 means "flatter than the reference".  With
# REF = JPEG XS gen 1 at 1.0 bpp this is the project goal stated as a picture.
# Differential mode does its own normalisation implicitly and switches --norm off.
os.makedirs(outdir, exist_ok=True)

def load(path, f):
    y, cb, cr = yuvio.planes(path, W, H, f, fmt, depth)
    r, g, b = yuvio.rgbish(y, cb, cr, W, fmt, depth)
    return dict(y=y, cb=cb, cr=cr, r=r, g=g, b=b, mid=1 << (depth - 1),
                cbf=yuvio.upchroma(cb, W, fmt), crf=yuvio.upchroma(cr, W, fmt))

s, d = load(src, F), load(dec, F)
rf = load(ref, F) if ref else None
rfp = load(ref, F - 1) if (ref and F > 0) else None
if ref: norm = 0
sp = load(src, F - 1) if F > 0 else None
dp = load(dec, F - 1) if F > 0 else None

cons = None
detail = None
print("frame %d  block %d  arm %s" % (F, blk, tag))
print("%-14s %-34s %7s %7s %7s %7s %7s" %
      ("measure", "what it measures", "mean", "p01", "worst", "<0.70", "<0.50"))
for name, fn, what in flatlib.MEASURES:
    r = fn(s, d, sp, dp, blk) if name == 'M15_temporal' else fn(s, d, blk)
    if rf is not None:
        rr = fn(s, rf, sp, rfp, blk) if name == 'M15_temporal' else fn(s, rf, blk)
        r = flatlib._ratio(r, rr, 1e-3)
    if norm:
        if detail is None:
            detail = flatlib.detail_of(s, blk)
        r = flatlib.normalise(r, detail)
    if maps:
        flatlib.render(r, os.path.join(outdir, "%s_f%d_%s.png" % (tag, F, name)), blk)
    st = dict(mean=float(r.mean()), p01=float(np.percentile(r, 1)),
              worst=float(r.min()), f70=float((r < 0.70).mean()),
              f50=float((r < 0.50).mean()))
    print("%-14s %-34s %7.3f %7.3f %7.3f %6.2f%% %6.2f%%" %
          (name, what, st['mean'], st['p01'], st['worst'], st['f70']*100, st['f50']*100))
    flat = (r < 0.70).astype(np.int32)
    cons = flat if cons is None else cons + flat

n = len(flatlib.MEASURES)
if maps:
    # consensus rendered on the SAME convention: black = no measure objects.
    flatlib.render(1.0 - cons / float(n), os.path.join(outdir, "%s_f%d_M00_CONSENSUS.png" % (tag, F)),
                   blk, lo=1.0 - 6.0/n, hi=1.0)
print("CONSENSUS      blocks called flat by >=6 of 15           %7d  (%.3f%%)" %
      ((cons >= 6).sum(), 100.0*(cons >= 6).mean()))
print("CONSENSUS      blocks called flat by >=10 of 15          %7d  (%.3f%%)" %
      ((cons >= 10).sum(), 100.0*(cons >= 10).mean()))
np.save(os.path.join(outdir, "%s_f%d_consensus.npy" % (tag, F)), cons)

#!/usr/bin/env python3
"""line15.py SRC DEC W H FRAME OUTDIR [--fmt][--depth][--cb 16][--sh 16]
            [--tag NAME] [--maps 0|1] [--ref REF.yuv]

Runs all fifteen horizontal-line detectors of h/linelib.py on one frame, writes
one full-frame map each plus a CONSENSUS map, and prints the ROW PROFILE of the
consensus by slice phase -- which is the number that says whether the lines are
the coding grid or the content.

With --ref, each detector is run on DEC and on REF and the map is the
DIFFERENCE, so "OMC's lines that JPEG XS does not have" is one command.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio, linelib

a = sys.argv
src, dec, W, H, F, outdir = a[1], a[2], int(a[3]), int(a[4]), int(a[5]), a[6]
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
cb    = int(a[a.index('--cb')+1])    if '--cb'    in a else 16
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
tag   = a[a.index('--tag')+1]        if '--tag'   in a else 'arm'
maps  = int(a[a.index('--maps')+1])  if '--maps'  in a else 1
ref   = a[a.index('--ref')+1]        if '--ref'   in a else None
os.makedirs(outdir, exist_ok=True)

def load(path, f):
    y, cbp, crp = yuvio.planes(path, W, H, f, fmt, depth)
    mid = 1 << (depth - 1)
    cbf, crf = yuvio.upchroma(cbp, W, fmt), yuvio.upchroma(crp, W, fmt)
    r = y + 1.5748 * (crf - mid); b = y + 1.8556 * (cbf - mid)
    g = y - 0.1873 * (cbf - mid) - 0.4681 * (crf - mid)
    return dict(y=y, cb=cbp, cr=crp, cbf=cbf, crf=crf, r=r, g=g, b=b, mid=mid)

s, d = load(src, F), load(dec, F)
sp = load(src, F-1) if F > 0 else None
dp = load(dec, F-1) if F > 0 else None
rf = load(ref, F) if ref else None
rfp = load(ref, F-1) if (ref and F > 0) else None

print("frame %d  colblock %d  slice_h %d  arm %s%s"
      % (F, cb, sh, tag, ("  (differential vs %s)" % os.path.basename(ref)) if ref else ""))
print("%-15s %-40s %9s %9s %9s" % ("detector", "what it detects", "mean", "p99.9", "max"))
cons = None
for name, fn, what in linelib.MEASURES:
    if name == 'L14_persist':
        v = fn(s, d, cb, sh, sp, dp)
        vr = fn(s, rf, cb, sh, sp, rfp) if rf is not None else None
    else:
        v = fn(s, d, cb, sh)
        vr = fn(s, rf, cb, sh) if rf is not None else None
    if vr is not None:
        v = v - vr
    if maps:
        linelib.render(v, os.path.join(outdir, "%s_f%d_%s.png" % (tag, F, name)), cb)
    p999 = float(np.percentile(v, 99.9))
    print("%-15s %-40s %9.3f %9.3f %9.3f" % (name, what, float(v.mean()), p999, float(v.max())))
    # Vote on the POSITIVE PART only, normalised to the detector's own 99.9th
    # percentile so no detector's units can dominate.
    #
    # The positive part is not a convenience.  A LINE is vertical structure the
    # decode HAS and the source does not; a negative excess means the decode is
    # SMOOTHER there, which is a flattening defect (sect.54) and not a line.
    # Voting on the signed value let the smoothing -- which is everywhere at
    # 0.5 bpp -- drive the consensus median negative, and every ratio taken
    # against it was meaningless.  L11_lost_edge is the one detector that
    # deliberately measures the missing-edge half, and it already returns it as
    # a positive score.
    nv = np.maximum(v, 0.0) / max(p999, 1e-9)
    cons = nv if cons is None else cons + nv
cons /= len(linelib.MEASURES)
if maps:
    linelib.render(cons, os.path.join(outdir, "%s_f%d_L00_CONSENSUS.png" % (tag, F)), cb, sat=1.0)
rowp = cons.mean(1)
prof = np.zeros(sh); cnt = np.zeros(sh)
for r in range(len(rowp)):
    prof[r % sh] += rowp[r]; cnt[r % sh] += 1
prof /= np.maximum(cnt, 1)
med = float(np.median(prof))
print("\nCONSENSUS row profile by slice phase (median %.4f):" % med)
print("  phase:" + "".join("%8d" % p for p in range(sh)))
print("  score:" + "".join("%8.4f" % v for v in prof))
print("  excess:" + "".join("%+7.0f%%" % (100.0 * (v / max(med, 1e-9) - 1)) for v in prof))
print("LINE INDEX (max phase / median phase) = %.3f   [1.00 = no row phase is special]"
      % (prof.max() / max(med, 1e-9)))
np.save(os.path.join(outdir, "%s_f%d_lineconsensus.npy" % (tag, F)), cons)

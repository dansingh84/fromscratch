#!/usr/bin/env python3
"""flatattr.py SRC DEC REF W H FRAME [--fmt][--depth][--blk 8][--sh 16][--k 10]

WHERE the flattening is, and WHAT the flattened blocks have in common.

Takes the consensus of h/flat15.py in DIFFERENTIAL mode (DEC against REF, both
against SRC) and asks four attribution questions of the blocks it selects,
because "here is a map" is not a diagnosis:

  1. Are they where the SOURCE is busiest?      -> a rate explanation
  2. Are they aligned to the slice grid?        -> a coding-structure explanation
  3. Are they chroma-led or luma-led?           -> which plane to look at
  4. Do they sit still frame to frame?          -> structural vs flicker

Every one of the four has a null model printed beside it, because a
concentration is only evidence if it beats what uniform placement would give.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio, flatlib

a = sys.argv
src, dec, ref, W, H, F = a[1], a[2], a[3], int(a[4]), int(a[5]), int(a[6])
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
blk   = int(a[a.index('--blk')+1])   if '--blk'   in a else 8
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
K     = int(a[a.index('--k')+1])     if '--k'     in a else 10

def load(path, f):
    y, cb, cr = yuvio.planes(path, W, H, f, fmt, depth)
    r, g, b = yuvio.rgbish(y, cb, cr, W, fmt, depth)
    return dict(y=y, cb=cb, cr=cr, r=r, g=g, b=b, mid=1 << (depth - 1),
                cbf=yuvio.upchroma(cb, W, fmt), crf=yuvio.upchroma(cr, W, fmt))

def consensus(f):
    s, d, r = load(src, f), load(dec, f), load(ref, f)
    sp = load(src, f-1) if f > 0 else None
    dp = load(dec, f-1) if f > 0 else None
    rp = load(ref, f-1) if f > 0 else None
    cons = None; per = {}
    for name, fn, _ in flatlib.MEASURES:
        x = fn(s, d, sp, dp, blk) if name == 'M15_temporal' else fn(s, d, blk)
        y_ = fn(s, r, sp, rp, blk) if name == 'M15_temporal' else fn(s, r, blk)
        q = flatlib._ratio(x, y_, 1e-3)
        per[name] = q
        fl = (q < 0.70).astype(np.int32)
        cons = fl if cons is None else cons + fl
    return cons, per, s

cons, per, s = consensus(F)
sel = cons >= K
nh, nw = cons.shape
print("frame %d  block %d  selected %d of %d blocks (%.2f%%) at >=%d/15" %
      (F, blk, sel.sum(), sel.size, 100.0*sel.mean(), K))
if sel.sum() == 0:
    raise SystemExit(0)

# ---- 1. rate explanation: source detail decile of the selected blocks
det = flatlib.detail_of(s, blk)
q = np.quantile(det, np.linspace(0, 1, 11))
hist = [int(((det >= q[i]) & (det < q[i+1]) & sel).sum()) for i in range(10)]
tot  = [int(((det >= q[i]) & (det < q[i+1])).sum()) for i in range(10)]
print("\n1. SOURCE-DETAIL decile of the selected blocks (null = 10%% each)")
print("   decile:  " + " ".join("%5d" % i for i in range(1, 11)))
print("   share %%: " + " ".join("%5.1f" % (100.0*h/max(sel.sum(),1)) for h in hist))
print("   hit  %%: " + " ".join("%5.1f" % (100.0*h/max(t,1)) for h, t in zip(hist, tot)))

# ---- 2. coding structure: distance to the nearest slice boundary
rows = np.arange(nh) * blk
dist = np.minimum(rows % sh, (sh - rows % sh) % sh)
print("\n2. SLICE-GRID alignment (slice_h=%d)" % sh)
for dv in sorted(set(dist.tolist())):
    m = np.zeros_like(sel); m[dist == dv, :] = True
    print("   rows at distance %2d from a slice edge: %5.2f%% selected (all rows %5.2f%%)"
          % (dv, 100.0*sel[m].mean(), 100.0*sel.mean()))

# ---- 3. which measures drive it
print("\n3. WHICH MEASURES call the selected blocks flat (share of selected)")
order = sorted(per.items(), key=lambda kv: -float((kv[1][sel] < 0.70).mean()))
for name, q_ in order:
    print("   %-14s %6.1f%%   median ratio on selected %6.3f  (whole frame %6.3f)"
          % (name, 100.0*float((q_[sel] < 0.70).mean()),
             float(np.median(q_[sel])), float(np.median(q_))))

# ---- 4. do the selected blocks stay put?
if F > 0:
    cons_p, _, _ = consensus(F-1)
    selp = cons_p >= K
    inter = float((sel & selp).sum())
    print("\n4. TEMPORAL PERSISTENCE  frame %d n=%d, frame %d n=%d, overlap %d"
          % (F, sel.sum(), F-1, selp.sum(), int(inter)))
    print("   Jaccard %.3f   (a structural artifact stays put; a rate artifact moves;"
          % (inter / max((sel | selp).sum(), 1)))
    print("    anything in between is seen as FLICKER)")

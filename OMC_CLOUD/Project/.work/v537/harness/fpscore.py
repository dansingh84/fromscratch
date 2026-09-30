#!/usr/bin/env python3
"""fpscore.py SRC.yuv DEC.yuv REF.yuv W H NFRAMES [--fmt 422] [--depth 10]

The REPAIR FOOTPRINT and its TEMPORAL VARIATION.

`footprint` = mean |DEC - REF| over every luma sample, on the 10-bit scale,
where REF is the same cell with the in-gamut repair disabled.  It is exactly
"how much did the repair disturb the picture", and it cannot be gamed by moving
damage between artifact classes.

`flicker` = the standard deviation of the PER-FRAME footprint, plus the largest
frame-to-frame step.  It is here because a repair that disturbs different
amounts on successive frames is seen as FLICKER even when each frame in
isolation is acceptable -- and the owner's original report (2026-08-25) was that
the artifacts "move between locations frame to frame".  A fix that lowers the
mean while raising the step has not helped.

Lower is better on every column.
"""
import sys, numpy as np
a=sys.argv
src,dec,ref,W,H,N = a[1],a[2],a[3],int(a[4]),int(a[5]),int(a[6])
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
per = W*H*2 if fmt=='422' else W*H*3
k = 1024.0/(1<<depth); pf=[]; hi=0.0; p999=[]
for f in range(N):
    d=np.fromfile(dec,dtype='<u2',count=per,offset=f*per*2)[:W*H].astype(np.float32)
    r=np.fromfile(ref,dtype='<u2',count=per,offset=f*per*2)[:W*H].astype(np.float32)
    v=np.abs(d-r)*k
    pf.append(float(v.mean())); hi=max(hi,float(v.max())); p999.append(float(np.percentile(v,99.9)))
pf=np.array(pf); step=float(np.abs(np.diff(pf)).max()) if len(pf)>1 else 0.0
print("footprint %.3f  flicker sd %.3f  max step %.3f  p99.9 %.1f  worst %.0f  | per-frame %s"
      % (pf.mean(), pf.std(), step, float(np.mean(p999)), hi,
         " ".join("%.2f"%x for x in pf)))

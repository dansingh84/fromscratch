#!/usr/bin/env python3
"""strongest.py SRC.yuv DEC.yuv W H FRAME REGIONS.txt [--fmt 422] [--depth 10]

Rank the OWNER-VERIFIED detector's own boxes by HOW STRONG their colour is on
the error map, which is the question a human asks when looking at it -- not by
mean error, which under-weights a small, fully-saturated box.

The map saturates at +-SAT (40 codes on the 10-bit scale), so a "strong" box is
one whose pixels are AT the saturation limit.  Per region this reports:
  sat%   fraction of the region's pixels at |err| >= SAT  (fully red or blue)
  p95    the 95th percentile of |err| in the region
  peak   the largest |err| in the region
ranked by sat% x area, i.e. how much fully-saturated colour the box contains.
"""
import sys, re, numpy as np
a=sys.argv
src,dec,W,H,f,reg = a[1],a[2],int(a[3]),int(a[4]),int(a[5]),a[6]
fmt   = a[a.index('--fmt')+1] if '--fmt' in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
SAT   = 40.0*(1<<depth)/1024.0
per = W*H*2 if fmt=='422' else W*H*3
s=np.fromfile(src,dtype='<u2',count=per,offset=f*per*2)[:W*H].reshape(H,W).astype(float)
d=np.fromfile(dec,dtype='<u2',count=per,offset=f*per*2)[:W*H].reshape(H,W).astype(float)
e=d-s
rows=[]
for ln in open(reg):
    m=re.search(r'(\w+)\s+rows\s+(\d+)-\s*(\d+)\s+cols\s+(\d+)-\s*(\d+)\s+area\s+(\d+)\s+err\s+([-+0-9.]+)\s+src\s+([0-9.]+)\s+slice\s+(\d+)',ln)
    if not m: continue
    k=m.group(1); y0,y1,x0,x1=int(m.group(2)),int(m.group(3)),int(m.group(4)),int(m.group(5))
    sl=int(m.group(9))
    box=e[y0:y1+1,x0:x1+1]; ab=np.abs(box)
    satpx=int((ab>=SAT).sum()); n=box.size
    rows.append((satpx, satpx/max(n,1), np.percentile(ab,95), ab.max(),
                 box.mean(), k, y0,y1,x0,x1, n, sl, (y0%16)//4))
rows.sort(reverse=True)
print("  %-6s %-11s %-11s %6s %6s %5s %6s %6s %5s %2s"
      %("kind","rows","cols","satpx","sat%","p95","peak","mean","slice","br"))
for r in rows[:15]:
    satpx,satf,p95,pk,mn,k,y0,y1,x0,x1,n,sl,br = r
    print("  %-6s %4d-%-6d %4d-%-6d %6d %5.1f%% %5.0f %6.0f %+6.1f %5d %2d"
          %(k,y0,y1,x0,x1,satpx,satf*100,p95,pk,mn,sl,br))
tot=sum(r[0] for r in rows)
print("  fully-saturated pixels inside detected regions: %d over %d regions"%(tot,len(rows)))

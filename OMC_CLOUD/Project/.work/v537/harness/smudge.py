#!/usr/bin/env python3
"""smudge.py SRC.yuv DEC.yuv W H FRAME OUT.png [--sh 16] [--fmt 422]
                                               [--depth 10] [--ratio 0.70]

DETAIL LOSS, the second face of the repair's footprint -- and the one a level
metric is blind to by construction.

A WASH shifts a block's mean and leaves its texture alone.  A SMUDGE leaves the
mean alone and removes the texture: the local standard deviation collapses while
the block mean stays ~0, so `levelmap.py` and `blotch.py` both read it as clean
while the picture visibly loses detail.  On the per-pixel error map a smudge is
STRONG colour with ZERO mean -- exactly the boxes that were dismissed as "just
noise" on 2026-08-25 before the owner pointed out they are visible in the render
as a smudge overlaying the image.

Per (slice_h/4) x 32 block this computes sd(decoded)/sd(source) and boxes every
connected region where that ratio falls below --ratio while the source itself
has real texture (sd >= 8 codes; a flat block cannot be smudged).

This is PROJECT_CONSTRAINTS G4 territory (flattening), measured directly.
"""
import sys, numpy as np
from PIL import Image, ImageDraw
from collections import deque
a=sys.argv
src,dec,W,H,f,out = a[1],a[2],int(a[3]),int(a[4]),int(a[5]),a[6]
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
RAT   = float(a[a.index('--ratio')+1]) if '--ratio' in a else 0.70
SDMIN = 8.0*(1<<depth)/1024.0
per = W*H*2 if fmt=='422' else W*H*3
s=np.fromfile(src,dtype='<u2',count=per,offset=f*per*2)[:W*H].reshape(H,W).astype(float)
d=np.fromfile(dec,dtype='<u2',count=per,offset=f*per*2)[:W*H].reshape(H,W).astype(float)
bh,bw = sh//4, 32
nh,nw = H//bh, W//bw
def blocks(x):
    return x[:nh*bh,:nw*bw].reshape(nh,bh,nw,bw)
sd_s = blocks(s).std(axis=(1,3)); sd_d = blocks(d).std(axis=(1,3))
ratio = np.where(sd_s>=SDMIN, sd_d/np.maximum(sd_s,1e-6), 1.0)
mask = (ratio < RAT) & (sd_s >= SDMIN)
e=(d-s)*(1024.0/(1<<depth))
img=np.zeros((H,W,3),np.uint8)
img[...,0]=(np.clip( e/40.0,0,1)*255).astype(np.uint8)
img[...,2]=(np.clip(-e/40.0,0,1)*255).astype(np.uint8)
img[...,1]=((1-np.clip(np.abs(e)/40.0,0,1))*40).astype(np.uint8)
im=Image.fromarray(img); dr=ImageDraw.Draw(im)
seen=np.zeros(mask.shape,bool); regs=[]
for y,x in zip(*np.nonzero(mask)):
    if seen[y,x]: continue
    q=deque([(y,x)]); seen[y,x]=True; cells=[]
    while q:
        cy,cx=q.popleft(); cells.append((cy,cx))
        for ny,nx in ((cy+1,cx),(cy-1,cx),(cy,cx+1),(cy,cx-1)):
            if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:
                seen[ny,nx]=True; q.append((ny,nx))
    ys=[c[0] for c in cells]; xs=[c[1] for c in cells]
    y0,y1,x0,x1 = min(ys)*bh,(max(ys)+1)*bh-1, min(xs)*bw,(max(xs)+1)*bw-1
    r = float(np.mean([ratio[c] for c in cells])); area=len(cells)*bh*bw
    regs.append(((1.0-r)*area, r, y0,y1,x0,x1, area,
                 float(np.mean([sd_s[c] for c in cells])), y0//sh, (y0%sh)//bh))
    dr.rectangle([x0-2,y0-2,x1+2,y1+2], outline=(255,140,0))
im.save(out)
regs.sort(reverse=True)
print("%s: %d SMUDGE regions (sd ratio < %.2f), detail-loss energy %.0f"
      % (out, len(regs), RAT, sum(r[0] for r in regs)))
for r in regs[:10]:
    print("   rows %4d-%-4d cols %4d-%-4d area %6d  sd ratio %.2f  src sd %5.1f  slice %3d br %d"
          % (r[2],r[3],r[4],r[5],r[6],r[1],r[7],r[8],r[9]))

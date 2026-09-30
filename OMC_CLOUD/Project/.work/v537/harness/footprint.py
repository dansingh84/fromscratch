#!/usr/bin/env python3
"""footprint.py SRC.yuv DEC.yuv REF.yuv W H FRAME OUT.png [--fmt 422]
                                                          [--depth 10] [--sh 16]

THE REPAIR'S FOOTPRINT -- the sharpest attribution available, with no threshold
about what KIND of artifact it is.

DEC is the cell as shipped.  REF is the same cell with the in-gamut repair
disabled (`--gamut-strict 0`) -- a DIAGNOSTIC arm that breaks A4 and is never a
reference point for quality, only for attribution.  Everything that differs
between them is the repair and nothing else: same source, same rate, same
bitstream syntax, same everything.

It renders |DEC - REF| per (slice_h/4) x 32 block and boxes every connected
region above the threshold.  A box here is not "strong colour" and not "a wrong
level" -- it is, exactly, WHERE THE REPAIR CHANGED THE PICTURE AND BY HOW MUCH.
That is the list to fix, in the order printed.
"""
import sys, numpy as np
from PIL import Image, ImageDraw
from collections import deque
a=sys.argv
src,dec,ref,W,H,f,out = a[1],a[2],a[3],int(a[4]),int(a[5]),int(a[6]),a[7]
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
THR   = float(a[a.index('--thr')+1]) if '--thr'   in a else 6.0
per = W*H*2 if fmt=='422' else W*H*3
def rd(p): return np.fromfile(p,dtype='<u2',count=per,offset=f*per*2)[:W*H].reshape(H,W).astype(float)
s,d,r = rd(src),rd(dec),rd(ref)
k = 1024.0/(1<<depth)
bh,bw = sh//4, 32; nh,nw = H//bh, W//bw
def blk(x): return x[:nh*bh,:nw*bw].reshape(nh,bh,nw,bw)
foot = np.abs(blk(d-r)).mean(axis=(1,3))*k          # mean |change the repair made|
lvl  = blk(d-r).mean(axis=(1,3))*k                  # and its signed part
sd_r, sd_d = blk(r).std(axis=(1,3)), blk(d).std(axis=(1,3))
tex  = np.where(sd_r>4, sd_d/np.maximum(sd_r,1e-6), 1.0)
img=np.zeros((H,W,3),np.uint8)
fp = np.repeat(np.repeat(foot,bh,0),bw,1)
sg = np.repeat(np.repeat(lvl ,bh,0),bw,1)
img[...,0]=(np.clip(np.where(sg>=0,fp,0)/40.0,0,1)*255).astype(np.uint8)
img[...,2]=(np.clip(np.where(sg< 0,fp,0)/40.0,0,1)*255).astype(np.uint8)
im=Image.fromarray(img); dr=ImageDraw.Draw(im)
mask = foot > THR
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
    y0,y1,x0,x1=min(ys)*bh,(max(ys)+1)*bh-1,min(xs)*bw,(max(xs)+1)*bw-1
    fm=float(np.mean([foot[c] for c in cells])); lm=float(np.mean([lvl[c] for c in cells]))
    tm=float(np.mean([tex[c] for c in cells])); ar=len(cells)*bh*bw
    regs.append((fm*ar, fm, lm, tm, y0,y1,x0,x1, ar, y0//sh, (y0%sh)//bh))
    dr.rectangle([x0-2,y0-2,x1+2,y1+2], outline=(255,255,0) if abs(lm)>8 else (255,140,0))
im.save(out)
regs.sort(reverse=True)
print("%s: %d regions the repair changed by more than %.0f codes; total footprint %.0f"
      % (out,len(regs),THR,sum(r[0] for r in regs)))
print("   %-11s %-11s %7s %7s %7s %6s %5s %2s"%("rows","cols","area","|chg|","signed","tex","slice","br"))
for g in regs[:12]:
    _,fm,lm,tm,y0,y1,x0,x1,ar,sl,br=g
    print("   %4d-%-6d %4d-%-6d %7d %7.1f %+7.1f %6.2f %5d %2d"%(y0,y1,x0,x1,ar,fm,lm,tm,sl,br))

#!/usr/bin/env python3
"""strongmap.py SRC.yuv DEC.yuv W H FRAME OUT.png [--fmt 422] [--depth 10]
                                                  [--sh 16] [--dens 0.15]
                                                  [--ref REF.yuv]

BOX EVERY STRONG RED/BLUE.  No mean filter, no shape prior, no size prior
beyond one block.

The 2026-08-25 mistake this replaces: `washmap.py` boxed only regions whose
block MEAN level was wrong, on the reasoning that a mean of zero means "not a
level shift, therefore not the artifact".  The owner corrected it -- a region
can have zero mean and still be the artifact, because the second face of it is
a SMUDGE: the texture is destroyed while the level stays right, and in the
render it reads as a smear overlaying the picture rather than as a dark patch.
Strong colour is strong colour; box it and then explain it, never the reverse.

A block is STRONG if at least `dens` of its pixels are at the map's saturation
limit (|err| >= 40 codes on the 10-bit scale).  Connected strong blocks form a
region.  Each region is then CLASSIFIED, and the class only changes the label
and the box colour -- never whether it is drawn:

  WASH   |mean level| > 8 codes            -> the level is wrong   (yellow)
  SMUDGE sd(dec)/sd(src) < 0.7             -> the texture is gone  (orange)
  BOTH   both of the above                 -> (red)
  RATE   neither                           -> strong colour that is neither    (grey)

With --ref REF.yuv (the same cell decoded with the in-gamut repair DISABLED --
`--gamut-strict 0`, which is a DIAGNOSTIC arm and never a reference point for
quality) each region also reports how much of its saturation the repair ADDED
over that floor.  That is the number that says whether a box is the codec's
rate or the encoder's policy.
"""
import sys, numpy as np
from PIL import Image, ImageDraw
from collections import deque
a=sys.argv
src,dec,W,H,f,out = a[1],a[2],int(a[3]),int(a[4]),int(a[5]),a[6]
fmt   = a[a.index('--fmt')+1]          if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1])   if '--depth' in a else 10
sh    = int(a[a.index('--sh')+1])      if '--sh'    in a else 16
DENS  = float(a[a.index('--dens')+1])  if '--dens'  in a else 0.15
ref   = a[a.index('--ref')+1]          if '--ref'   in a else None
SAT   = 40.0*(1<<depth)/1024.0
SDMIN = 8.0*(1<<depth)/1024.0
per = W*H*2 if fmt=='422' else W*H*3
def rd(p): return np.fromfile(p,dtype='<u2',count=per,offset=f*per*2)[:W*H].reshape(H,W).astype(float)
s,d = rd(src), rd(dec)
r = rd(ref) if ref else None
bh,bw = sh//4, 32
nh,nw = H//bh, W//bw
def blk(x): return x[:nh*bh,:nw*bw].reshape(nh,bh,nw,bw)
e = d-s
satb  = (np.abs(blk(e))>=SAT).mean(axis=(1,3))
meanb = blk(e).mean(axis=(1,3))*(1024.0/(1<<depth))
sd_s, sd_d = blk(s).std(axis=(1,3)), blk(d).std(axis=(1,3))
ratio = np.where(sd_s>=SDMIN, sd_d/np.maximum(sd_s,1e-6), 1.0)
refsat = (np.abs(blk(r-s))>=SAT).mean(axis=(1,3)) if r is not None else None
mask = satb >= DENS
en=(e)*(1024.0/(1<<depth))
img=np.zeros((H,W,3),np.uint8)
img[...,0]=(np.clip( en/40.0,0,1)*255).astype(np.uint8)
img[...,2]=(np.clip(-en/40.0,0,1)*255).astype(np.uint8)
img[...,1]=((1-np.clip(np.abs(en)/40.0,0,1))*40).astype(np.uint8)
im=Image.fromarray(img); dr=ImageDraw.Draw(im)
COL={'WASH':(255,255,0),'SMUDGE':(255,150,0),'BOTH':(255,60,60),'RATE':(170,170,170)}
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
    mn = float(np.mean([meanb[c] for c in cells]))
    rt = float(np.mean([ratio[c]  for c in cells]))
    st = float(np.mean([satb[c]   for c in cells]))
    rf = float(np.mean([refsat[c] for c in cells])) if refsat is not None else float('nan')
    w = abs(mn)>8; g = rt<0.70
    k = 'BOTH' if (w and g) else 'WASH' if w else 'SMUDGE' if g else 'RATE'
    regs.append((st*len(cells), k, y0,y1,x0,x1, len(cells)*bh*bw, st, mn, rt, rf, y0//sh))
    dr.rectangle([x0-2,y0-2,x1+2,y1+2], outline=COL[k])
im.save(out)
regs.sort(reverse=True)
from collections import Counter
print("%s: %d STRONG regions  (classes: %s)"
      % (out, len(regs), dict(Counter(r[1] for r in regs))))
hdr = "   %-6s %-11s %-11s %7s %6s %7s %6s"%("class","rows","cols","area","sat%","level","sd")
if ref: hdr += " %8s %8s"%("ref sat%","repair+")
print(hdr)
for r in regs[:14]:
    _,k,y0,y1,x0,x1,ar,st,mn,rt,rf,sl = r
    line = "   %-6s %4d-%-6d %4d-%-6d %7d %5.1f%% %+7.1f %6.2f"%(k,y0,y1,x0,x1,ar,st*100,mn,rt)
    if ref: line += " %7.1f%% %+7.1f%%"%(rf*100,(st-rf)*100)
    print(line)

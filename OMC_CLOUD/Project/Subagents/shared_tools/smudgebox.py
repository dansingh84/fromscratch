#!/usr/bin/env python3
"""smudgebox.py SRC DEC W H FRAME OUT.png [--fmt 422] [--depth 10] [--blk 16] [--zoom x0,y0,x1,y1]
Box what the eye calls a SMUDGE: a textured area whose fine structure came back wrong -- the source
block has real high-pass energy, the decode's high-pass no longer matches it (correlation < 0.5), and
the error carries at least half the block's texture energy.  Groups of adjacent such blocks are boxed on
the COLOUR decode (luma yellow, chroma green/blue on their own planes).  No shape prior.
"""
import sys, numpy as np
from PIL import Image, ImageDraw
from collections import deque
a=sys.argv[1:]; fmt,depth,B,zoom='422',10,16,None
for k,c in (('--fmt',str),('--depth',int),('--blk',int),('--zoom',str)):
    if k in a: i=a.index(k); v=c(a[i+1]); del a[i:i+2]; fmt,depth,B,zoom=(v if k=='--fmt' else fmt),(v if k=='--depth' else depth),(v if k=='--blk' else B),(v if k=='--zoom' else zoom)
src,dec,W,H,f,out=a[0],a[1],int(a[2]),int(a[3]),int(a[4]),a[5]
Wc=W//2 if fmt=='422' else W; fw=W*H+2*Wc*H; mx=(1<<depth)-1
def planes(p):
    d=np.fromfile(p,dtype=np.uint16)[f*fw:(f+1)*fw].astype(np.float64)
    return d[:W*H].reshape(H,W), d[W*H:W*H+Wc*H].reshape(H,Wc), d[W*H+Wc*H:].reshape(H,Wc)
def hp(p): return p-(np.roll(p,1,0)+np.roll(p,-1,0)+np.roll(p,1,1)+np.roll(p,-1,1))/4
def blk(x,bh,bw): hh,ww=x.shape; nh,nw=hh//bh,ww//bw; return x[:nh*bh,:nw*bw].reshape(nh,bh,nw,bw)
def rgb(y,cb,cr):
    if Wc!=W: cb=np.repeat(cb,2,axis=1)[:,:W]; cr=np.repeat(cr,2,axis=1)[:,:W]
    yy=(y/mx*255-16*255/256)*(255/219); c1=(cb/mx-0.5)*255*(255/224); c2=(cr/mx-0.5)*255*(255/224)
    return np.clip(np.stack([yy+1.5748*c2, yy-0.1873*c1-0.4681*c2, yy+1.8556*c1],-1),0,255).astype(np.uint8)
def comps(mask):
    nh,nw=mask.shape; seen=np.zeros_like(mask,bool); out=[]
    for y in range(nh):
        for x in range(nw):
            if mask[y,x] and not seen[y,x]:
                q=deque([(y,x)]); seen[y,x]=True; cells=[]
                while q:
                    cy,cx=q.popleft(); cells.append((cy,cx))
                    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny,nx=cy+dy,cx+dx
                        if 0<=ny<nh and 0<=nx<nw and mask[ny,nx] and not seen[ny,nx]: seen[ny,nx]=True; q.append((ny,nx))
                out.append(cells)
    return out
S=planes(src); D=planes(dec); img=Image.fromarray(rgb(*D)); dr=ImageDraw.Draw(img); tot=[]
for pi,(pn,col) in enumerate((("Y",(255,255,0)),("Cb",(0,255,0)),("Cr",(0,160,255)))):
    s,d=S[pi],D[pi]; bw=B if s.shape[1]==W else B//2
    hs,hd=hp(s),hp(d); he=hp(d-s)
    es=(blk(hs,B,bw)**2).sum(axis=(1,3)); ed=(blk(hd,B,bw)**2).sum(axis=(1,3)); ee=(blk(he,B,bw)**2).sum(axis=(1,3))
    num=(blk(hs,B,bw)*blk(hd,B,bw)).sum(axis=(1,3)); corr=num/(np.sqrt(es*ed)+1e-9)
    tex=es>0.5*np.median(es)
    smudge=tex&(corr<0.5)&(ee>0.5*es)
    groups=[g for g in comps(smudge) if len(g)>=2]
    scale=W//s.shape[1]
    for g in groups:
        ys=[c[0] for c in g]; xs=[c[1] for c in g]
        dr.rectangle([min(xs)*bw*scale,min(ys)*B,(max(xs)+1)*bw*scale-1,(max(ys)+1)*B-1],outline=col,width=2)
    tot.append("%s: %d smudge blocks of %d textured (%.0f%%), %d groups"%(pn,smudge.sum(),tex.sum(),100*smudge.sum()/max(tex.sum(),1),len(groups)))
print(' | '.join(tot)); img.save(out)
if zoom:
    x0,y0,x1,y1=[int(v) for v in zoom.split(',')]; img.crop((x0,y0,x1,y1)).resize(((x1-x0)*2,(y1-y0)*2),Image.NEAREST).save(out.replace('.png','_zoom.png'))
print("wrote",out)

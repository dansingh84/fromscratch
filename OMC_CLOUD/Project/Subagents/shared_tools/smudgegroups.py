#!/usr/bin/env python3
"""smudgegroups.py — OWNER METHOD (2026-09-02): the level map (mean signed error per LL support block,
levelmap.py), with the source's own level structure deducted, and every LARGER GROUPING of red/blue
blocks (either sign, dense) boxed = a smudge.
usage: smudgegroups.py SRC DEC W H FRAME OUTPREFIX [--sh 8] [--fmt 422] [--thr 12] [--dens 0.5] [--minblk 8]
Writes OUTPREFIX_boxed.png (colour decode with groups boxed, Y yellow / Cb green / Cr blue),
OUTPREFIX_lvl_Y.png (level map with boxes), OUTPREFIX_srclvl_Y.png (source level structure), and prints
per plane: groups, total blocks, largest, and the list (rows/cols in pixels)."""
import sys, numpy as np
from PIL import Image, ImageDraw
from collections import deque
a=sys.argv[1:]; sh,fmt,thr,dens,minblk=8,'422',12.0,0.5,8
for k,cast in (('--sh',int),('--fmt',str),('--thr',float),('--dens',float),('--minblk',int)):
    if k in a: i=a.index(k); v=cast(a[i+1]); del a[i:i+2]; sh,fmt,thr,dens,minblk=[v if k==kk else old for kk,old in zip(('--sh','--fmt','--thr','--dens','--minblk'),(sh,fmt,thr,dens,minblk))]
src,dec,W,H,f,outp=a[0],a[1],int(a[2]),int(a[3]),int(a[4]),a[5]
Wc=W//2 if fmt=='422' else W; fw=W*H+2*Wc*H; mx=1023
def planes(p):
    d=np.fromfile(p,dtype=np.uint16)[f*fw:(f+1)*fw].astype(np.float64)
    return d[:W*H].reshape(H,W), d[W*H:W*H+Wc*H].reshape(H,Wc), d[W*H+Wc*H:].reshape(H,Wc)
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
                    for dy in (-1,0,1):
                        for dx in (-1,0,1):
                            ny,nx=cy+dy,cx+dx
                            if 0<=ny<nh and 0<=nx<nw and mask[ny,nx] and not seen[ny,nx]: seen[ny,nx]=True; q.append((ny,nx))
                out.append(cells)
    return out
def boxsum(m,kh,kw):
    p=np.pad(m.astype(np.float64),((kh//2,kh//2),(kw//2,kw//2)))
    c=np.cumsum(np.cumsum(p,0),1); c=np.pad(c,((1,0),(1,0)))
    return c[kh:,kw:]-c[:-kh,kw:]-c[kh:,:-kw]+c[:-kh,:-kw]
S=planes(src); D=planes(dec); img=Image.fromarray(rgb(*D)); dr=ImageDraw.Draw(img)
bh,bw=sh//4,32; KH,KW=5,3
for pi,(name,col,scale) in enumerate((("Y",(255,255,0),1),("Cb",(0,255,0),W//Wc),("Cr",(0,160,255),W//Wc))):
    s=S[pi]; d=D[pi]; hh,ww=s.shape; nh,nw=hh//bh,ww//bw
    e=(d-s)[:nh*bh,:nw*bw].reshape(nh,bh,nw,bw).mean(axis=(1,3))
    # the source's own level structure: block mean minus the 3x3-block neighbourhood mean (what a viewer
    # sees as content), rendered for comparison; the error map is already source-deducted (d - s)
    sb=s[:nh*bh,:nw*bw].reshape(nh,bh,nw,bw).mean(axis=(1,3)); nb=boxsum(sb,3,3)/9.0; srclvl=sb-nb
    strong=np.abs(e)>thr
    density=boxsum(strong,KH,KW)/float(KH*KW)
    mask=density>=dens
    groups=[g for g in comps(mask) if len(g)>=minblk]
    lines=[]
    for g in groups:
        ys=[c[0] for c in g]; xs=[c[1] for c in g]
        y0,y1,x0,x1=min(ys)*bh,(max(ys)+1)*bh-1,min(xs)*bw*scale,(max(xs)+1)*bw*scale-1
        dr.rectangle([x0,y0,x1,y1],outline=col,width=2); lines.append("rows %d-%d cols %d-%d blocks %d"%(y0,y1,x0,x1,len(g)))
    print("%s: %d groups, %d blocks, largest %d  [thr %g dens %g]"%(name,len(groups),sum(len(g) for g in groups),max((len(g) for g in groups),default=0),thr,dens))
    for l in lines[:12]: print("   ",l)
    if name=="Y":
        for tag,m in (("lvl",e),("srclvl",srclvl)):
            im=np.zeros((nh*bh,nw*bw,3),np.uint8); big=np.repeat(np.repeat(m,bh,0),bw,1)
            im[...,0]=(np.clip(big/20.0,0,1)*255).astype(np.uint8); im[...,2]=(np.clip(-big/20.0,0,1)*255).astype(np.uint8)
            I=Image.fromarray(im); D2=ImageDraw.Draw(I)
            if tag=="lvl":
                for g in groups:
                    ys=[c[0] for c in g]; xs=[c[1] for c in g]; D2.rectangle([min(xs)*bw,min(ys)*bh,(max(xs)+1)*bw-1,(max(ys)+1)*bh-1],outline=(255,255,0),width=2)
            I.save(f"{outp}_{tag}_Y.png")
img.save(f"{outp}_boxed.png"); print("wrote",outp)

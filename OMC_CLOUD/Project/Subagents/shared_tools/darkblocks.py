#!/usr/bin/env python3
"""darkblocks.py SRC DEC W H NFRAMES [--fmt 422] [--depth 10]  -- the OWNER'S BLACK SMUDGE class, per frame:
8x8 luma blocks whose mean level is darker than the source by > 20 codes (and > 40), plus the bright side.
Prints one line per frame and a summary (intra frame 0 separately)."""
import sys, numpy as np
a=sys.argv[1:]; fmt,depth='422',10
if '--fmt' in a: i=a.index('--fmt'); fmt=a[i+1]; del a[i:i+2]
if '--depth' in a: i=a.index('--depth'); depth=int(a[i+1]); del a[i:i+2]
src,dec,W,H,nf=a[0],a[1],int(a[2]),int(a[3]),int(a[4])
Wc=W//2 if fmt=='422' else W; fw=W*H+2*Wc*H; sc=1024.0/(1<<depth)
S=np.fromfile(src,dtype=np.uint16); D=np.fromfile(dec,dtype=np.uint16); nf=min(nf,len(D)//fw,len(S)//fw)
rows=[]
for f in range(nf):
    s=S[f*fw:f*fw+W*H].reshape(H,W).astype(np.float64); d=D[f*fw:f*fw+W*H].reshape(H,W).astype(np.float64)
    e=((d-s)*sc)[:H//8*8,:W//8*8].reshape(H//8,8,W//8,8).mean(axis=(1,3))
    rows.append(((e<-20).sum(),(e<-40).sum(),(e>20).sum(),(e>40).sum()))
f0=rows[0]; rest=rows[1:] or [(0,0,0,0)]
print("DARK[f0 %d/%d rest-mean %.1f/%.1f max %d] BRIGHT[f0 %d/%d rest-mean %.1f/%.1f]"%(f0[0],f0[1],np.mean([r[0] for r in rest]),np.mean([r[1] for r in rest]),max(r[0] for r in rest),f0[2],f0[3],np.mean([r[2] for r in rest]),np.mean([r[3] for r in rest])))

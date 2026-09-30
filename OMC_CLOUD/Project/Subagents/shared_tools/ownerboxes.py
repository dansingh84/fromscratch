#!/usr/bin/env python3
"""ownerboxes.py DEC.yuv [label] -- the owner's marked boxes (am720/owner_boxes.json, 720p frame 2) measured on a decode:
grille set (y>=640) and rest set: mean |err|, HP energy ratio, chroma |err|, and NEG-free summary."""
import sys, json, numpy as np
A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms'; W,H,Wc=1280,720,640; fw=W*H+2*Wc*H; f=2
dec=sys.argv[1]; label=sys.argv[2] if len(sys.argv)>2 else dec
bx=json.load(open('/home/user/fromscratch/OMC_CLOUD/Project/.work/sandbox/sbx_texture/out/am720/owner_boxes.json'))['red']
def planes(p):
    d=np.fromfile(p,dtype=np.uint16)[f*fw:(f+1)*fw].astype(np.float64)
    return d[:W*H].reshape(H,W), d[W*H:W*H+Wc*H].reshape(H,Wc), d[W*H+Wc*H:].reshape(H,Wc)
def hp(p): return p-(np.roll(p,1,0)+np.roll(p,-1,0)+np.roll(p,1,1)+np.roll(p,-1,1))/4
S=planes(f"{A}/dng_1280x720_422_10.yuv"); D=planes(dec); hs,hd=hp(S[0]),hp(D[0])
def stats(bs):
    ab=[];hr=[];ce=[];co=[]
    for (x0,y0,x1,y1) in bs:
        s=S[0][y0:y1+1,x0:x1+1]; d=D[0][y0:y1+1,x0:x1+1]; ab.append(np.abs(d-s).mean())
        a=hs[y0:y1+1,x0:x1+1]; b=hd[y0:y1+1,x0:x1+1]; hr.append((b**2).mean()/((a**2).mean()+1e-9)); co.append((a*b).sum()/(np.sqrt((a**2).sum()*(b**2).sum())+1e-9))
        cs=np.concatenate([S[1][y0:y1+1,x0//2:x1//2+1].ravel(),S[2][y0:y1+1,x0//2:x1//2+1].ravel()]); cd=np.concatenate([D[1][y0:y1+1,x0//2:x1//2+1].ravel(),D[2][y0:y1+1,x0//2:x1//2+1].ravel()])
        ce.append(np.abs(cd-cs).mean())
    return np.mean(ab),np.median(hr),np.median(co),np.mean(ce)
g=[b for b in bx if b[1]>=640]; r=[b for b in bx if b[1]<640]
for name,bs in (("grille",g),("rest",r)):
    ab,hr,co,ce=stats(bs); print("%-28s %-7s luma|err| %5.1f  HP ratio %.2f  HP corr %.2f  chroma|err| %5.1f"%(label,name,ab,hr,co,ce))

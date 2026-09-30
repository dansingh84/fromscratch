#!/usr/bin/env python3
"""[SA7] boundary-phase error statistic: mean |decode-source| in the columns at control-point
phase vs mid-span phase, per plane.  A NUMBER ONLY -- the eye decides on the renders.
usage: phase.py SRC DEC W H FMT DEPTH FRAME SPACING_LUMA"""
import sys, numpy as np
src,dec,W,H,fmt,dep,f,SPL = sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),sys.argv[5],int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8])
Wc = W if fmt=='444' else W//2
fw = W*H+2*Wc*H
def pl(p):
    d=np.fromfile(p,dtype=np.uint16)[f*fw:(f+1)*fw].astype(np.float64)
    return d[:W*H].reshape(H,W), d[W*H:W*H+Wc*H].reshape(H,Wc), d[W*H+Wc*H:].reshape(H,Wc)
S=pl(src); D=pl(dec)
out=[]
for i,nm in enumerate(('Y','Cb','Cr')):
    e=np.abs(D[i]-S[i]); w=e.shape[1]; sp=SPL if i==0 else max(SPL*Wc//W,1)
    cp=e[:, ::sp].mean(); mid=e[:, sp//2::sp].mean(); allm=e.mean()
    out.append("%s cp=%.3f mid=%.3f all=%.3f  cp/mid=%.4f"%(nm,cp,mid,allm,cp/max(mid,1e-9)))
print("PHASE f%d sp=%d  "%(f,SPL)+" | ".join(out))

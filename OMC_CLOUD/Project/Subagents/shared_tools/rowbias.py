#!/usr/bin/env python3
"""mean SIGNED error (decode - source) per plane by row phase class: rows 0-11 vs 12,13,14,15.
usage: rowbias.py SRC DEC W H FMT DEPTH FRAME"""
import sys, numpy as np
src,dec=sys.argv[1],sys.argv[2]; W,H=int(sys.argv[3]),int(sys.argv[4]); fmt=sys.argv[5]; dep=int(sys.argv[6]); fr=int(sys.argv[7]); sh=16
cw = W if fmt=='444' else W//2; fw=W*H+2*cw*H
def load(p):
    d=np.fromfile(p,dtype='<u2',count=(fr+1)*fw)[fr*fw:(fr+1)*fw].astype(np.float64)
    return [d[:W*H].reshape(H,W), d[W*H:W*H+cw*H].reshape(H,cw), d[W*H+cw*H:].reshape(H,cw)]
s,d=load(src),load(dec); out=[]
for pi,pn in enumerate('Y Cb Cr'.split()):
    e=d[pi]-s[pi]; ph=np.arange(H)%sh
    inner=e[ph<12].mean(); r=[e[ph==k].mean() for k in (12,13,14,15)]
    out.append(f"{pn}: inner {inner:+.3f} r12 {r[0]:+.3f} r13 {r[1]:+.3f} r14 {r[2]:+.3f} r15 {r[3]:+.3f}")
print("   bias " + " | ".join(out))

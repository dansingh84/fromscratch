#!/usr/bin/env python3
"""quality.py REF.yuv DIST.yuv W H N [fmt] -- per-plane PSNR (C5: never
luma-only).  Planar u16 LE, frame-sequential, 4:2:2 or 4:4:4."""
import sys, numpy as np
r,d,W,H,N = sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5])
fmt = sys.argv[6] if len(sys.argv)>6 else '422'
depth = int(sys.argv[7]) if len(sys.argv)>7 else 10
cw = W//2 if fmt=='422' else W
per = W*H + 2*cw*H
A=np.fromfile(r,dtype='<u2',count=per*N).astype(np.float64)
B=np.fromfile(d,dtype='<u2',count=per*N).astype(np.float64)
peak=(1<<depth)-1
out=[]
for k,(o,n) in enumerate([(0,W*H),(W*H,cw*H),(W*H+cw*H,cw*H)]):
    se=0.0; tot=0
    for f in range(N):
        a=A[f*per+o:f*per+o+n]; b=B[f*per+o:f*per+o+n]
        se+=float(((a-b)**2).sum()); tot+=n
    mse=se/tot
    out.append(99.0 if mse==0 else 10*np.log10(peak*peak/mse))
print("Y %.3f Cb %.3f Cr %.3f" % tuple(out))

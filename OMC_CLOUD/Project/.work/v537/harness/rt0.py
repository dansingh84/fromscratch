#!/usr/bin/env python3
"""rt0.py REC.cdr DEC.yuv W H CODED_H NFRAMES FMT DEPTH -- the C4 check.

`--recon` writes the encoder's reconstruction in CDR form: the BIASED,
UNCLIPPED, UNCROPPED coded raster (omc1.h).  The decoder's output is the
non-normative projection of it: clip(v - OMC_PIX_BIAS, 0, 2^depth - 1),
cropped to the display height.  rt = 0 means those two agree on every sample
of every plane -- so the projection has to be applied before comparing, not
skipped.  Prints "rt=0" or the number of disagreeing samples per plane.
"""
import sys, numpy as np
BIAS = 2048
rec,dec,W,H,CH,N,fmt,depth = (sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),
                              int(sys.argv[5]),int(sys.argv[6]),sys.argv[7],int(sys.argv[8]))
cw = W//2 if fmt=='422' else W
maxv=(1<<depth)-1
rper = W*CH + 2*cw*CH
dper = W*H  + 2*cw*H
bad=[0,0,0]
for f in range(N):
    R=np.fromfile(rec,dtype='<u2',count=rper,offset=f*rper*2).astype(np.int32)
    D=np.fromfile(dec,dtype='<u2',count=dper,offset=f*dper*2).astype(np.int32)
    ro=0; do=0
    for p,(pw,) in enumerate([(W,),(cw,),(cw,)]):
        r=R[ro:ro+pw*CH].reshape(CH,pw)[:H]; ro+=pw*CH
        d=D[do:do+pw*H].reshape(H,pw);       do+=pw*H
        bad[p]+=int((np.clip(r-BIAS,0,maxv)!=d).sum())
print("rt=0" if sum(bad)==0 else "rt=NONZERO Y%d Cb%d Cr%d"%tuple(bad))

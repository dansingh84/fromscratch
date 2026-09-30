#!/usr/bin/env python3
"""levelmap.py SRC.yuv DEC.yuv W H FRAME OUT.png [--sh 16] [--fmt 422|444|400] [--sat 20]
                                                  [--depth 10] [--plane Y|Cb|Cr|all]

The COHERENCE view of sect.50.7's error map.  artifactmap.py renders the
per-pixel signed error, which at 0.5 bpp is dense everywhere on detailed
content -- ordinary quantisation noise saturates it just as a real blotch does,
so the eye cannot separate "this level is wrong" from "this area is noisy".
This renders the MEAN signed error over each LL support block
((slice_h/4) rows x 32 plane columns), which is zero for noise and non-zero
only when a LEVEL is wrong.  Red = too bright, blue = too dark, saturating at
+-SAT codes on the 10-bit scale.  A clean picture is BLACK here.

v5.3.5 (sect.B3): `--plane` selects the plane.  The v5.3 tool read the Y plane
only (LEDGER_v5_3 sect.78.2: chroma level error had never been rendered).
`--plane all` writes three files, OUT with `_Y`, `_Cb`, `_Cr` inserted before
the extension.  A 4:2:2 chroma map is half the luma width; it is written at its
own raster, NOT stretched, so a block is still one LL support.  Default Y, so
every existing call is unchanged.
"""
import sys, os, numpy as np
from PIL import Image
a=sys.argv
src,dec,W,H,f,out = a[1],a[2],int(a[3]),int(a[4]),int(a[5]),a[6]
fmt = a[a.index('--fmt')+1] if '--fmt' in a else '422'
sh  = int(a[a.index('--sh')+1]) if '--sh' in a else 16
SAT = float(a[a.index('--sat')+1]) if '--sat' in a else 20.0
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
plane = a[a.index('--plane')+1] if '--plane' in a else 'Y'
CW = 0 if fmt == '400' else (W//2 if fmt=='422' else W)
per = W*H + 2*CW*H
dims = {'Y': (H, W), 'Cb': (H, CW), 'Cr': (H, CW)}
offs = {'Y': 0, 'Cb': W*H, 'Cr': W*H + CW*H}
S=np.fromfile(src,dtype='<u2',count=per,offset=f*per*2).astype(np.float64)
D=np.fromfile(dec,dtype='<u2',count=per,offset=f*per*2).astype(np.float64)
if S.size < per or D.size < per:
    raise SystemExit("levelmap.py: short read at frame %d" % f)
planes = ('Y','Cb','Cr') if plane == 'all' else (plane,)
if fmt == '400': planes = tuple(p for p in planes if p == 'Y')
bh,bw=sh//4,32
for pn in planes:
    hh, ww = dims[pn]
    s = S[offs[pn]:offs[pn]+hh*ww].reshape(hh, ww)
    d = D[offs[pn]:offs[pn]+hh*ww].reshape(hh, ww)
    e=(d-s)*(1024.0/(1<<depth))
    nh,nw=hh//bh,ww//bw
    blk=e[:nh*bh,:nw*bw].reshape(nh,bh,nw,bw).mean(axis=(1,3))
    big=np.repeat(np.repeat(blk,bh,0),bw,1)
    img=np.zeros((nh*bh,nw*bw,3),np.uint8)
    img[...,0]=(np.clip( big/SAT,0,1)*255).astype(np.uint8)
    img[...,2]=(np.clip(-big/SAT,0,1)*255).astype(np.uint8)
    if plane == 'all':
        root, ext = os.path.splitext(out); o = "%s_%s%s" % (root, pn, ext or '.png')
    else:
        o = out
    Image.fromarray(img).save(o)
    print("%s [%s]: worst block %+.1f, blocks |mean|>20: %d, >40: %d"
          % (o, pn, blk.ravel()[int(np.argmax(np.abs(blk)))], int((np.abs(blk)>20).sum()), int((np.abs(blk)>40).sum())))

#!/usr/bin/env python3
"""render.py SRC.yuv W H FRAME OUT.png [--fmt 422] [--depth 10]

Full-frame, full-resolution 16-bit RGB render of one frame of a planar Y'CbCr
raw, BT.709 limited range -- the same convention eyekit_2026-08-23 used, so a
render from this tool is directly comparable with the kit's PNGs.
No downscaling, no cropping: PROJECT_CONSTRAINTS sect.E requires both.
"""
import sys, numpy as np
from PIL import Image
a=sys.argv
src,W,H,f,out = a[1],int(a[2]),int(a[3]),int(a[4]),a[5]
fmt   = a[a.index('--fmt')+1]   if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
cw = W//2 if fmt=='422' else W
per = W*H + 2*cw*H
d = np.fromfile(src, dtype='<u2', count=per, offset=f*per*2).astype(np.float64)
y  = d[:W*H].reshape(H,W)
cb = d[W*H:W*H+cw*H].reshape(H,cw)
cr = d[W*H+cw*H:].reshape(H,cw)
if fmt=='422':                       # co-sited horizontal upsample, matching derive.py's inverse
    cb = np.repeat(cb,2,axis=1); cr = np.repeat(cr,2,axis=1)
s  = 1 << (depth-8)
yn  = (y  - 16*s) / (219.0*s)
cbn = (cb - 128*s) / (224.0*s)
crn = (cr - 128*s) / (224.0*s)
KR,KB = 0.2126,0.0722; KG = 1-KR-KB
r = yn + 2*(1-KR)*crn
b = yn + 2*(1-KB)*cbn
g = (yn - KR*r - KB*b)/KG
rgb = np.clip(np.dstack([r,g,b]),0,1)
a16 = (rgb*65535+0.5).astype('>u2')   # 16-bit big-endian; PIL cannot write 48-bit RGB,
                                      # so the PNG is emitted directly below
import zlib, struct
def png48(path, arr):
    h,w,_ = arr.shape
    raw = b''.join(b'\x00' + arr[y].tobytes() for y in range(h))
    def chunk(t,d):
        c = t+d
        return struct.pack('>I',len(d)) + c + struct.pack('>I', zlib.crc32(c)&0xffffffff)
    hdr = struct.pack('>IIBBBBB', w,h,16,2,0,0,0)
    open(path,'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',hdr)
                          + chunk(b'IDAT', zlib.compress(raw,6)) + chunk(b'IEND',b''))
png48(out, a16)
print("%s: %dx%d 16-bit RGB, frame %d" % (out,W,H,f))

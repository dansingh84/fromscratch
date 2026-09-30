#!/usr/bin/env python3
"""zoom3.py OUT.png Y0 Y1 X0 X1 SCALE SRC.yuv DEC1.yuv DEC2.yuv W H FRAME
Stacks SOURCE / arm1 / arm2 crops of the same region at SCALE x, labelled, so a
region can be judged by eye without hunting for it in a full frame."""
import sys, numpy as np
from PIL import Image, ImageDraw
a=sys.argv
out=a[1]; y0,y1,x0,x1,sc=map(int,a[2:7]); paths=a[7:10]; W,H,f=int(a[10]),int(a[11]),int(a[12])
def rgb(p):
    per=W*H*2
    d=np.fromfile(p,dtype='<u2',count=per,offset=f*per*2).astype(np.float64)
    y=d[:W*H].reshape(H,W); cw=W//2
    cb=np.repeat(d[W*H:W*H+cw*H].reshape(H,cw),2,axis=1)
    cr=np.repeat(d[W*H+cw*H:].reshape(H,cw),2,axis=1)
    s=4.0; yn=(y-16*s)/(219*s); cbn=(cb-128*s)/(224*s); crn=(cr-128*s)/(224*s)
    KR,KB=0.2126,0.0722; KG=1-KR-KB
    r=yn+2*(1-KR)*crn; b=yn+2*(1-KB)*cbn; g=(yn-KR*r-KB*b)/KG
    return (np.clip(np.dstack([r,g,b]),0,1)*255+.5).astype(np.uint8)[y0:y1,x0:x1]
labs=['SOURCE','OMC v5.0','OMC v5.1']
crops=[Image.fromarray(rgb(p)).resize(((x1-x0)*sc,(y1-y0)*sc),Image.NEAREST) for p in paths]
cw_,ch=crops[0].size
im=Image.new('RGB',(cw_, ch*3+3*22+8),(20,20,20)); d=ImageDraw.Draw(im)
for i,(c,l) in enumerate(zip(crops,labs)):
    yy=i*(ch+22)+18
    d.text((6, yy-16), "%s   rows %d-%d cols %d-%d  frame %d  (%dx)"%(l,y0,y1,x0,x1,f,sc), fill=(255,255,0))
    im.paste(c,(0,yy))
im.save(out); print(out, im.size)

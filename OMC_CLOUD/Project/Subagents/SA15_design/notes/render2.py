# render2.py SRC DEC W H FRAME OUTPREFIX [--S 8] [--fmt 422]
# Per plane (Y, Cb, Cr): signed error maps at +-16 and +-2 codes (red = decode brighter, blue = darker,
# white = 0) with a colour legend, unmarked and with the slice grid; level map (mean signed error per
# 8x8 block) at +-2 codes with legend; slice-edge strips: 16 rows centred on 4 slice boundaries, full width,
# magnified x4 vertically (one picture row = 4 output rows), error at +-2 codes and the decoded plane.
import sys, numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0,__file__.rsplit('/',1)[0])
import seq2
def cmap(e,sat):
    t=np.clip(e/sat,-1,1); r=np.where(t>0,255,255*(1+t)); b=np.where(t<0,255,255*(1-t)); g=255*(1-np.abs(t))
    return np.stack([r,g,b],-1).astype(np.uint8)
def legend(w,sat,label):
    x=np.linspace(-sat,sat,w)[None,:].repeat(22,0); im=Image.fromarray(cmap(x,sat)); d=ImageDraw.Draw(im)
    d.text((3,5),f'-{sat}',fill=(0,0,0)); d.text((w//2-3,5),'0',fill=(0,0,0)); d.text((w-34,5),f'+{sat}',fill=(0,0,0))
    full=Image.new('RGB',(w+260,22),(255,255,255)); full.paste(im,(0,0)); ImageDraw.Draw(full).text((w+6,5),label,fill=(0,0,0))
    return full
def withlegend(im,sat,label):
    lg=legend(min(360,im.width-260) if im.width>620 else 200,sat,label)
    out=Image.new('RGB',(max(im.width,lg.width),im.height+26),(255,255,255)); out.paste(lg,(0,2)); out.paste(im,(0,26)); return out
def grid(im,S,mag):
    d=ImageDraw.Draw(im)
    for r in range(0,im.height//mag,S): d.line([(0,r*mag),(im.width,r*mag)],fill=(0,150,0),width=1)
    return im
def main(src,dec,W,H,f,outp,S=8,fmt=422):
    Sp=seq2.read(src,W,H,f,fmt); Dp=seq2.read(dec,W,H,f,fmt)
    for nm,s,d in zip(('Y','Cb','Cr'),Sp,Dp):
        e=d.astype(float)-s; Sc=S if nm=='Y' or fmt!=420 else S//2
        for sat in (16,2):
            im=Image.fromarray(cmap(e,sat))
            withlegend(im,sat,f'{nm} decode-source, codes').save(f'{outp}_err{sat}_{nm}.png')
            withlegend(grid(im.copy(),Sc,1),sat,f'{nm} decode-source, codes, slice grid').save(f'{outp}_err{sat}_{nm}_grid.png')
        h8,w8=e.shape[0]//8,e.shape[1]//8
        lv=e[:h8*8,:w8*8].reshape(h8,8,w8,8).mean(axis=(1,3))
        im=Image.fromarray(cmap(lv,2)).resize((w8*8,h8*8),Image.NEAREST)
        withlegend(grid(im,Sc,1),2,f'{nm} level map (8x8 mean error), codes').save(f'{outp}_lvl2_{nm}_grid.png')
        # slice-edge strips x4 vertical
        H_=e.shape[0]; strips=[]
        for k in (H_//(4*Sc)*Sc, H_//(2*Sc)*Sc, 3*H_//(4*Sc)*Sc, (H_//Sc-1)*Sc):
            r0=max(0,k-8); r1=min(H_,k+8)
            a=Image.fromarray(cmap(e[r0:r1],2)).resize((e.shape[1],(r1-r0)*4),Image.NEAREST)
            dd=np.clip((d[r0:r1]-d.min())*255.0/max(1,d.max()-d.min()),0,255).astype(np.uint8)
            b=Image.fromarray(dd).convert('RGB').resize((e.shape[1],(r1-r0)*4),Image.NEAREST)
            for im_ in (a,b):
                dr=ImageDraw.Draw(im_); y=(k-r0)*4; dr.line([(0,y),(8,y)],fill=(0,150,0),width=2); dr.line([(im_.width-8,y),(im_.width,y)],fill=(0,150,0),width=2)
            strips+=[a,b]
        tot=Image.new('RGB',(e.shape[1],sum(x.height+6 for x in strips)),(255,255,255)); y=0
        for x in strips: tot.paste(x,(0,y)); y+=x.height+6
        withlegend(tot,2,f'{nm} slice-edge strips x4 vertical: error / decode (edge = green ticks)').save(f'{outp}_edges_{nm}.png')
if __name__=='__main__':
    a=sys.argv; S=int(a[a.index('--S')+1]) if '--S' in a else 8; fmt=int(a[a.index('--fmt')+1]) if '--fmt' in a else 422
    main(a[1],a[2],int(a[3]),int(a[4]),int(a[5]),a[6],S,fmt)

# Renders for one frame: per-plane signed error maps (red = decode brighter, blue = darker, +-SAT codes,
# with colour legend), unmarked and with slice grid; per-plane level maps (mean signed error per 4x4
# minus nothing -- raw level); per-row mean error profiles magnified x4 (one row = 4 output px).
import sys, numpy as np
from PIL import Image, ImageDraw
from common import read_frame
def cmap(e,sat):
    t=np.clip(e/sat,-1,1); r=np.where(t>0,255,255*(1+t)); b=np.where(t<0,255,255*(1-t)); g=255*(1-np.abs(t))
    return np.stack([r,g,b],-1).astype(np.uint8)
def legend(w,sat):
    x=np.linspace(-sat,sat,w)[None,:].repeat(20,0); im=Image.fromarray(cmap(x,sat)); d=ImageDraw.Draw(im)
    d.text((2,4),f'-{sat}',fill=(0,0,0)); d.text((w//2-4,4),'0',fill=(0,0,0)); d.text((w-40,4),f'+{sat}',fill=(0,0,0)); return im
def main(src,dec,W,H,f,outp,SH=16,sat=16,mag=4):
    S=read_frame(src,W,H,f); D=read_frame(dec,W,H,f)
    for nm,s,d in zip(('Y','Cb','Cr'),S,D):
        e=d.astype(float)-s
        for grid in (0,1):
            im=Image.fromarray(cmap(e,sat))
            if mag>1: im=im.resize((im.width*mag,im.height*mag),Image.NEAREST)
            if grid:
                dr=ImageDraw.Draw(im)
                for r in range(0,e.shape[0],SH): dr.line([(0,r*mag),(im.width,r*mag)],fill=(0,160,0),width=1)
            full=Image.new('RGB',(im.width,im.height+24),(255,255,255)); full.paste(im,(0,24)); full.paste(legend(min(400,im.width),sat),(0,2))
            full.save(f'{outp}_err_{nm}{"_grid" if grid else ""}.png')
        # level map: mean signed error per 4x4 block, x(4*mag)
        h4,w4=e.shape[0]//4,e.shape[1]//4
        lv=e[:h4*4,:w4*4].reshape(h4,4,w4,4).mean(axis=(1,3))
        im=Image.fromarray(cmap(lv,sat/4)).resize((w4*4*mag,h4*4*mag),Image.NEAREST)
        dr=ImageDraw.Draw(im)
        for r in range(0,e.shape[0],SH): dr.line([(0,r*mag),(im.width,r*mag)],fill=(0,160,0),width=1)
        im.save(f'{outp}_lvl_{nm}_grid.png')
        # row profile: mean |e| and mean e per row, one row = mag px
        ae=np.abs(e).mean(1); se=e.mean(1); Hh=e.shape[0]
        prof=np.full((Hh*mag,420,3),255,np.uint8); m=max(ae.max(),1e-6)
        for r in range(Hh):
            n=int(ae[r]/m*200); prof[r*mag:(r+1)*mag,:n]=(80,80,80)
            c=int(210+np.clip(se[r]/m*200,-200,200)); a,b=sorted((210,c)); prof[r*mag:(r+1)*mag,a:b+1]=(200,0,0) if c>210 else (0,0,200)
            if r%SH==0: prof[r*mag,:]=(0,160,0)
        Image.fromarray(prof).save(f'{outp}_rowprof_{nm}.png')
if __name__=='__main__':
    a=sys.argv; main(a[1],a[2],int(a[3]),int(a[4]),int(a[5]),a[6],int(a[7]) if len(a)>7 else 16)

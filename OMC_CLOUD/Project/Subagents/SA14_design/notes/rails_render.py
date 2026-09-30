"""Rail content: NEST v3 (rails + injective dequantisation) vs the same indices decoded by the plain inverse +
pixel clip, intra, full frames, all planes.  Writes renders (unmarked + _grid) and |diff| maps; prints NEG, PSNR,
and whether every differing sample moved toward the source."""
import sys, os, subprocess, numpy as np
sys.path.insert(0,'.')
import importlib, nv3, common14 as cm, t_v3_intra as tv
from PIL import Image
SCR=sys.argv[1]; OUT='../renders'; T='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools'
def cases():
    p,dep=cm.read_frame('dng720',8)
    g=[np.clip((x-200)*5//2,0,1023) if i==0 else np.clip(512+(x-512)*2,0,1023) for i,x in enumerate(p)]
    yield 'railgraded720', g, 1280, 720
    p,dep=cm.read_frame('gfx',8); yield 'cfgfx', p, 448, 256
def code(planes, D0, rails):
    ys=[]; clip=[]; bits=0
    for X in planes:
        lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,1023,np.int64)
        sh=tv.shifts(X.shape,D0); P=tv.intra_params(X,sh)
        q,qt=nv3.encode3(X,P,lo,hi,rails=rails); y,_=nv3.decode(q,qt,P,lo,hi); ys.append(y); bits+=nv3.bits3(q,qt)
        if not rails:
            leaf=nv3.leaves(q,P); _,(tlo,thi)=nv3.windows(nv3.upd_values(leaf,nv3.railmask(q)),lo,hi); P.cp_top=tlo.copy()
            sv=nv3.idq_r; nv3.idq_r=lambda pred,qq,s,l,h: pred+(qq<<s)
            yb,_=nv3.decode(q,qt,P,lo-10**7,hi+10**7); nv3.idq_r=sv; clip.append(np.clip(yb,0,1023))
    return ys, clip, bits
def save(planes, W, H, path):
    np.concatenate([p.ravel() for p in planes]).astype('<u2').tofile(path)
def png_render(yuv, W, H, name):
    subprocess.run(['python3',T+'/render.py',yuv,str(W),str(H),'0',f'{OUT}/{name}.png'],check=True)
def diffmap(a, b, name, W, H, gain=8):
    d=np.abs(a[0]-b[0]).astype(float)
    c=np.maximum(np.repeat(np.abs(a[1]-b[1]),2,1),np.repeat(np.abs(a[2]-b[2]),2,1)).astype(float)
    img=np.stack([np.clip(d*gain,0,255),np.clip(c*gain,0,255),np.zeros_like(d)],-1).astype(np.uint8)
    Image.fromarray(img).save(f'{OUT}/{name}.png')
    g=img.copy(); g[::32,:]=[0,0,255]; g[:,::32]=[0,0,255]; Image.fromarray(g).save(f'{OUT}/{name}_grid.png')
for name,src,W,H in cases():
    for D0 in (48,128):
        ys,_,bn=code(src,D0,True); _,cl,bc=code(src,D0,False)
        sp=f'{SCR}/{name}_src.yuv'; npth=f'{SCR}/{name}_n.yuv'; cpth=f'{SCR}/{name}_c.yuv'
        save(src,W,H,sp); save(ys,W,H,npth); save(cl,W,H,cpth)
        neg=lambda d: subprocess.run(['bash',T+'/negscore.sh',sp,d,str(W),str(H),'422','10','1'],capture_output=True,text=True).stdout.strip().split()[-1]
        towards=away=0
        for i in range(3):
            dn=np.abs(ys[i]-src[i]); dc=np.abs(cl[i]-src[i]); m=ys[i]!=cl[i]
            towards+=int((m&(dn<dc)).sum()); away+=int((m&(dn>dc)).sum())
        ps=lambda y:[round(cm.psnr(src[i],y[i],10),2) for i in range(3)]
        print(f"{name} D0={D0}: bits(zeroth) NEST {bn/(W*H):.3f} clipcodec {bc/(W*H):.3f} | NEG NEST {neg(npth)} clip {neg(cpth)} | PSNR NEST {ps(ys)} clip {ps(cl)} | differing samples: toward source {towards}, away {away} | oob NEST {sum(int(((y<0)|(y>1023)).sum()) for y in ys)}",flush=True)
        tag=f'{name}_D{D0}'
        if not os.path.exists(f'{OUT}/{name}_source.png'): png_render(sp,W,H,f'{name}_source')
        png_render(npth,W,H,f'{tag}_nest'); png_render(cpth,W,H,f'{tag}_clipcodec')
        for p in (f'{tag}_nest',f'{tag}_clipcodec'):
            im=np.array(Image.open(f'{OUT}/{p}.png').convert('RGB')); im[::32,:]=[0,0,255]; im[:,::32]=[0,0,255]; Image.fromarray(im).save(f'{OUT}/{p}_grid.png')
        diffmap(ys,src,f'{tag}_absdiff_nest_vs_source',W,H); diffmap(cl,src,f'{tag}_absdiff_clip_vs_source',W,H); diffmap(ys,cl,f'{tag}_absdiff_nest_vs_clip',W,H)
        for f in (sp,npth,cpth): os.remove(f)

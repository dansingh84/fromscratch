import sys; sys.path.insert(0,'.')
import numpy as np, nv4, nv4frame as F, common14 as cm
def run(name, planes, dep, S, D0, lov=0, hiv=None):
    hiv=(1<<dep)-1 if hiv is None else hiv
    out=[]
    for pi,X in enumerate(planes):
        st=F.PlaneState(); nv4.STATS['sat']=0
        Y,Yc,b,same,tw=F.code_plane(X,dep,0,D0,S if pi==0 else S,st,None,None,set(),lov,hiv)
        out.append(f"{'Y Cb Cr'.split()[pi]}: bits/px {b/X.size:.4f} PSNR {cm.psnr(X,Y,dep):.3f} (clip same idx {cm.psnr(X,Yc,dep):.3f}) oob {int(((Y<lov)|(Y>hiv)).sum())} g2 {same} toward {tw[0]} away>1 {tw[1]} sat {nv4.STATS['sat']}")
    print(f"{name} D0={D0}: "+' | '.join(out),flush=True)
if __name__=='__main__':
    for D0 in (48,128):
        p,dep=cm.read_frame('dng720',8); run('dng720',p,dep,8,D0)
        g=[np.clip((x-200)*5//2,0,1023) if i==0 else np.clip(512+(x-512)*2,0,1023) for i,x in enumerate(p)]; run('graded720',g,10,8,D0)
        p,dep=cm.read_frame('spot',8); run('spot',p,dep,16,D0)
        p,dep=cm.read_frame('gfx',8); run('gfx',p,dep,16,D0)

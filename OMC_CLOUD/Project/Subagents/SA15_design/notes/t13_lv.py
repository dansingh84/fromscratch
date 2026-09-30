# 720p latency margin option: Lv=1 (4-line look-ahead) vs Lv=2 (8-line), intra, v2 codec, per plane
import numpy as np, cpp2, t2, tsx
from common import *
def gains(shape,Lv,c={}):
    if (shape,Lv) not in c: tsx.KV=tsx.KH='26'; c[(shape,Lv)]=t2.ts_gains(shape,5,Lv)
    return c[(shape,Lv)]
for cell,W,H,fr in [('dng720',1280,720,8),('gfx',448,256,3)]:
    P=read_frame(CELLS[cell][0],W,H,fr); res={}
    for Lv in (1,2):
        for kap in (40,46,52,58):
            b=0; ps=[]
            for p in P:
                g=gains(p.shape,Lv); T=cpp2.analysis(p,5,Lv)
                Df={k:np.full((v.shape[0],1),max(2.0,2**(kap/8)/np.sqrt(g[k]))) for k,v in T.items()}
                y,o=cpp2.code_plane(T,None,Df,None,0,1023,5,Lv,None,None); b+=sum(cond_entropy_bits(v[4]) for v in o.values()); ps.append(psnr(p,y))
            res.setdefault(Lv,[]).append((b/(W*H),ps))
    for k in range(3):
        x1=np.log([a for a,_ in res[1]]); y1=[c[k] for _,c in res[1]]; x2=np.log([a for a,_ in res[2]]); y2=[c[k] for _,c in res[2]]
        grid=np.linspace(max(x1.min(),x2.min()),min(x1.max(),x2.max()),20)
        d=np.mean(np.interp(grid,x1[::-1],y1[::-1])-np.interp(grid,x2[::-1],y2[::-1]))
        print(cell,'plane',k,'Lv1 minus Lv2 mean dPSNR %+.3f dB'%d,flush=True)

import numpy as np, cpp2
from common import *
import t2, tsx
Lh,Lv=5,2
def gains(shape,c={}):
    if shape not in c: tsx.KV=tsx.KH='26'; c[shape]=t2.ts_gains(shape,Lh,Lv)
    return c[shape]
def field(shape_by_key,kappa,g):
    return {k:np.full((shp[0],1),max(2.0,2**(kappa/8)/np.sqrt(g[k]))) for k,shp in shape_by_key.items()}
if __name__=='__main__':
    for cell,W,H,fr in [('dng720',1280,720,8),('spot',1920,1080,8)]:
        P=read_frame(CELLS[cell][0],W,H,fr); Pm=read_frame(CELLS[cell][0],W,H,fr-1)
        for kap in (40,48):
            line=[]; bits=0
            for p,pm in zip(P,Pm):
                g=gains(p.shape); T=cpp2.analysis(p,Lh,Lv); Df=field({k:v.shape for k,v in T.items()},kap,g)
                y,o=cpp2.code_plane(T,None,Df,None,0,1023,Lh,Lv,None,None)
                bits+=sum(cond_entropy_bits(v[4]) for v in o.values())
                T2=cpp2.analysis(y,Lh,Lv); y2,o2=cpp2.code_plane(T2,None,Df,None,0,1023,Lh,Lv,None,None)
                # decode from symbols
                SYM={k:v[4] for k,v in o.items()}
                yd,_=cpp2.code_plane(None,None,Df,None,0,1023,Lh,Lv,None,None,enc=False,SYM=SYM)
                # inter with prev frame as MC, full inter
                Tm=cpp2.analysis(pm,Lh,Lv); Dp={k:np.broadcast_to(Df[k],T[k].shape).copy() for k in T}
                it={k:np.ones(T[k].shape,bool) for k in T}; hf={k:np.zeros(T[k].shape,bool) for k in T}
                yi,oi=cpp2.code_plane(T,Tm,Df,Dp,0,1023,Lh,Lv,it,hf)
                Ti=cpp2.analysis(yi,Lh,Lv); yi2,_=cpp2.code_plane(Ti,Tm,Df,Dp,0,1023,Lh,Lv,it,hf)
                yi3,_=cpp2.code_plane(Ti,cpp2.analysis(np.roll(pm,5,0),Lh,Lv),Df,Dp,0,1023,Lh,Lv,it,hf)
                SYM={k:v[4] for k,v in oi.items()}
                yid,_=cpp2.code_plane(None,Tm,Df,Dp,0,1023,Lh,Lv,it,hf,enc=False,SYM=SYM,decstate={k:np.zeros(T[k].shape,bool) for k in T})
                line.append(f'psnr {psnr(p,y):.2f} g2 {(y2==y).all()} dec {(yd==y).all()} | inter psnr {psnr(p,yi):.2f} g2 {(yi2==yi).all()} otherref {(yi3==yi).all()} dec {(yid==yi).all()} oob {int(((y<0)|(y>1023)).sum()+((yi<0)|(yi>1023)).sum())}')
            print(cell,kap,f'intra bpp {bits/(W*H):.3f}',' || '.join(line),flush=True)

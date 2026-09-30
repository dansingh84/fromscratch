# open-loop (v2) vs closed-loop (v1) symbol determination, intra, matched entropy, per plane
import os; os.environ['DZ']='0.45'
import numpy as np, cpp, cpp2, tsx
from common import *
from t2v import gains, field
Lh,Lv=5,2; cpp.ALT=True
for cell,W,H,fr in [('dng720',1280,720,8),('spot',1920,1080,8),('gfx',448,256,3)]:
    P=read_frame(CELLS[cell][0],W,H,fr); res={'cl':[],'ol':[]}
    for kap in (36,42,48,54):
        for arm in ('cl','ol'):
            b=0; ps=[]
            for p in P:
                g=gains(p.shape)
                if arm=='ol':
                    T=cpp2.analysis(p,Lh,Lv); Df=field({k:v.shape for k,v in T.items()},kap,g)
                    y,o=cpp2.code_plane(T,None,Df,None,0,1023,Lh,Lv,None,None); b+=sum(cond_entropy_bits(v[4]) for v in o.values())
                else:
                    st={k:max(2.0,2**(kap/8)/np.sqrt(v)) for k,v in g.items()}
                    y,i=cpp.code_plane(p,st,Lh,Lv,0,1023); b+=sum(cond_entropy_bits(v) for v in i.values())
                ps.append(psnr(p,y))
            res[arm].append((b/(W*H),ps))
    out=[]
    for k in range(3):
        r=lambda a:(np.log([x for x,_ in res[a]]),[y[k] for _,y in res[a]])
        (xc,yc),(xo,yo)=r('cl'),r('ol')
        grid=np.linspace(max(xc.min(),xo.min()),min(xc.max(),xo.max()),20)
        out.append(np.mean(np.interp(grid,xo[::-1] if xo[0]>xo[-1] else xo,yo[::-1] if xo[0]>xo[-1] else yo)-np.interp(grid,xc[::-1] if xc[0]>xc[-1] else xc,yc[::-1] if xc[0]>xc[-1] else yc)))
    print(cell,'open-loop minus closed-loop, mean dPSNR over common rate range Y/Cb/Cr = %+.3f/%+.3f/%+.3f'%tuple(out),[(round(a,3),round(c[0],2)) for a,c in res['ol']],flush=True)

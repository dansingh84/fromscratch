import sys,numpy as np
from common import *
from t1_po_vs_53 import *
cell=sys.argv[1]; fr=int(sys.argv[2]); path,W,H=CELLS[cell]
P=read_frame(path,W,H,fr); Lh,Lv=5,2
Gs=[gains(p.shape,Lh,Lv) for p in P]
res={}
for name in ['53','po2','po4']:
    for D in [24,40,64,100,160]:
        tot=0; ps=[]
        for pi,p in enumerate(P):
            if name=='53': y,b=code53(p,D,Lh,Lv,Gs[pi])
            else: y,b=codepo(p,D,Lh,Lv,1.0,int(name[2]))
            tot+=b; ps.append(psnr(p,y))
        res.setdefault(name,[]).append((tot/(W*H),ps))
        print(f'{cell} f{fr} {name:4s} D={D:3d} bpp={tot/(W*H):.3f} Y/Cb/Cr={ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f}',flush=True)
# matched-rate deltas vs 53 at 0.5,1,2 bpp (log-rate interpolation)
for name in ['po2','po4']:
    for tb in [0.5,1.0,2.0]:
        out=[]
        for k in range(3):
            def at(n):
                r=np.array([a for a,_ in res[n]]); q=np.array([p[k] for _,p in res[n]]); o=np.argsort(r)
                return np.interp(np.log(tb),np.log(r[o]),q[o])
            out.append(at(name)-at('53'))
        print(f'{cell} {name} vs 53 @{tb} bpp dPSNR Y/Cb/Cr = {out[0]:+.2f}/{out[1]:+.2f}/{out[2]:+.2f}')

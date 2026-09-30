import sys; sys.path.insert(0,'.')
import numpy as np, nv3, common14 as cm, t_v3_intra as t
from ctx_bits import ctx_bits
for name,X,dep in (('rails10',cm.synth_rails(dep=10),10),('spot',cm.read_frame('spot',8)[0][0],10),('dng',cm.read_frame('dng1080',8)[0][0],10)):
    M=(1<<dep)-1; lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,M,np.int64)
    for D0 in (32,128,256):
        sh=t.shifts(X.shape,D0); P=t.intra_params(X,sh)
        out=[]
        for r in (True,False):
            q,qt=nv3.encode3(X,P,lo,hi,rails=r); y,_=nv3.decode(q,qt,P,lo,hi)
            b=sum(ctx_bits(nv3.symbols(v)) for d in q for v in d.values())+ctx_bits(nv3.symbols(qt))
            out.append((b/X.size,cm.psnr(X,y,dep)))
        print(f"{name} D0={D0}: context bits/px rails={out[0][0]:.4f} (psnr {out[0][1]:.2f}) | no-rails IDQ={out[1][0]:.4f} (psnr {out[1][1]:.2f})",flush=True)

import sys; sys.path.insert(0,'.')
import numpy as np, nv3, common14 as cm, t_v3_intra as tv
from ctx_bits import ctx_bits
p,dep=cm.read_frame('dng720',8)
src=[np.clip((x-200)*5//2,0,1023) if i==0 else np.clip(512+(x-512)*2,0,1023) for i,x in enumerate(p)]
for D0 in (48,128):
    bn=bc=0; aw=[]
    for X in src:
        lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,1023,np.int64)
        sh=tv.shifts(X.shape,D0); P=tv.intra_params(X,sh)
        for r in (True,False):
            q,qt=nv3.encode3(X,P,lo,hi,rails=r)
            b=sum(ctx_bits(nv3.symbols(v)) for d in q for v in d.values())+ctx_bits(nv3.symbols(qt))
            if r: bn+=b
            else: bc+=b
    print(f"railgraded720 D0={D0}: context bits/lumapx NEST {bn/(1280*720):.3f} clip codec {bc/(1280*720):.3f} ({100*(bn/bc-1):+.1f}%)")

"""Rail bit cost: context bits and quality per plane, rails-everywhere vs rails-only-where-the-index-is-zero vs no rails."""
import sys; sys.path.insert(0,'.')
import numpy as np, nv3, common14 as cm, t_v3_intra as tv
from ctx_bits import ctx_bits
def cells():
    p,dep=cm.read_frame('dng720',8)
    yield 'graded720',[np.clip((x-200)*5//2,0,1023) if i==0 else np.clip(512+(x-512)*2,0,1023) for i,x in enumerate(p)]
    p,dep=cm.read_frame('spot',8); yield 'spot(real rails)',p
for name,planes in cells():
    for D0 in (48,96,160):
        line=f"{name} D0={D0}:"
        for pi,X in enumerate(planes):
            lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,1023,np.int64)
            sh=tv.shifts(X.shape,D0); P=tv.intra_params(X,sh); res={}
            for tag,r,pol in (('none',False,'all'),('all',True,'all'),('zero',True,'zero')):
                nv3.RAILPOL=pol
                q,qt=nv3.encode3(X,P,lo,hi,rails=r); y,_=nv3.decode(q,qt,P,lo,hi)
                b=sum(ctx_bits(nv3.symbols(v)) for d in q for v in d.values())+ctx_bits(nv3.symbols(qt))
                res[tag]=(b,cm.psnr(X,y,10),int(sum((np.abs(v)>=nv3.RAIL).sum() for d in q for v in d.values())))
            nv3.RAILPOL='all'
            b0=res['none'][0]
            line+=f" | {'YBR'[pi]}: none {res['none'][1]:.2f}dB, all {100*(res['all'][0]/b0-1):+.1f}% {res['all'][1]:.2f}dB ({res['all'][2]} rails), zero-only {100*(res['zero'][0]/b0-1):+.1f}% {res['zero'][1]:.2f}dB ({res['zero'][2]})"
        print(line,flush=True)

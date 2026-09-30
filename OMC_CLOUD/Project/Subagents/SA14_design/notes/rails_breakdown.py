import sys, numpy as np
sys.path.insert(0,'.')
import nests as nest, enc3s as enc3, common14 as cm, ctx_bits as cb
cm.nest=nest
n2d,n1d=2,3
X=cm.synth_rails(dep=10); M=1023
lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,M,np.int64)
loI=np.full(X.shape,-nest.INF); hiI=np.full(X.shape,nest.INF)
D0=128; sh=cm.shifts_for(n2d,n1d,X.shape,D0)
for pol in (True,):
    enc3.SRC_ESC=pol
    ql,top,rec,st=enc3.encode(X,lo,hi,n2d,n1d,sh)
    desc,_=nest.read_description(ql,top)
    lev,(L,_,_)=nest.analysis(X,loI,hiI,n2d,n1d)
    print('policy',pol,'psnr',round(cm.psnr(X,rec,10),2))
    for i,(d,l) in enumerate(zip(desc[:-1],lev)):
        for n in d:
            a=cb.ctx_bits(d[n][1]); b=cb.ctx_bits(nest.Q(l[n]['val'],sh[(i,n)]))
            ne=int((np.abs(d[n][1])>=(1<<30)).sum()); nz=int((d[n][1]!=0).sum())
            print(f"  lev{i} {n}: NEST {a:9.0f} bits (esc {ne}, nonzero {nz}, shift {d[n][0]} vs plan {sh[(i,n)]})  clipref {b:9.0f}")
    a=cb.ctx_bits(desc[-1][2]); b=cb.ctx_bits(nest.Q(L,sh['top'])); print(f"  top NEST {a:.0f} clipref {b:.0f} shift {desc[-1][1]} vs {sh['top']}")

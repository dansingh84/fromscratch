"""Context-conditioned entropy (left/up neighbour class: escape / zero / nonzero) of the band symbols,
NEST (escapes as symbols) vs the clip reference (no escapes).  Shows whether rail escapes cost bits."""
import sys, numpy as np
sys.path.insert(0,'.')
import nests as nest, enc3s as enc3, common14 as cm
enc3.SRC_ESC = True
cm.nest = nest
n2d,n1d=2,3
def cls(sym):
    return np.where(sym>=(1<<30),2,np.where(sym<=-(1<<30),3,np.where(sym==0,0,1)))
def ctx_bits(sym):
    c=cls(sym)
    l=np.concatenate([np.zeros((c.shape[0],1),int),c[:,:-1]],1); u=np.concatenate([np.zeros((1,c.shape[1]),int),c[:-1]],0)
    ctx=l*4+u; tot=0.0
    for k in range(16):
        m=ctx==k
        if m.any(): tot+=nest.entropy_bits(sym[m])
    return tot
for name,X,dep in (('rails10',cm.synth_rails(dep=10),10),('spot',cm.read_frame('spot',8)[0][0],10),('gfx',cm.read_frame('gfx',8)[0][0],10)):
    M=(1<<dep)-1; lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,M,np.int64)
    loI=np.full(X.shape,-nest.INF); hiI=np.full(X.shape,nest.INF)
    for D0 in (48,128):
        sh=cm.shifts_for(n2d,n1d,X.shape,D0)
        ql,top,rec,st=enc3.encode(X,lo,hi,n2d,n1d,sh)
        desc,b0th=nest.read_description(ql,top)
        bn=sum(ctx_bits(v[1]) for d in desc[:-1] for v in d.values())+ctx_bits(desc[-1][2])
        lev,(L,_,_)=nest.analysis(X,loI,hiI,n2d,n1d)
        bc=sum(ctx_bits(nest.Q(d['val'],sh[(i,n)])) for i,l in enumerate(lev) for n,d in l.items() if n!='win')+ctx_bits(nest.Q(L,sh['top']))
        print(f"{name} D0={D0}: ctx bits/px NEST={bn/X.size:.4f} clipref={bc/X.size:.4f} ({100*(bn/bc-1):+.2f}%) ; zeroth-order NEST={b0th/X.size:.4f}",flush=True)

import os; os.environ['TABLES']='../out/tables_B.pkl'
import numpy as np, seq2
tabs=seq2.Tables(); A='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/cut24.yuv'
W,H=256,64; B=0.5*W*8
c=seq2.Codec(W,H,S=8,tabs=tabs); fr=seq2.read(A,W,H,0)
snap=c.snapshot(); c.ivl=c.ivl_of(fr); y=c._encode(fr,B); k1=list(c.frame_info['kap'])
c.restore(snap); c.ivl=c.ivl_of(y)
orig=c.lane_cost
def spy(k,cands,*a,**kw):
    r=orig(k,cands,*a,**kw)
    if len(cands)>3: print('k',k,'kp',a[2],'E',[x for x,e in zip(cands,r[2]) if e],'gen1',k1[k])
    return r
c.lane_cost=spy
y2=c._encode(y,B,None,recover_only=True); print('rec',c.frame_info['kap'],'miss',c.recov_miss,'same pic',all((a==b).all() for a,b in zip(y,y2)))
# test gen1's own chain exactness directly
c.restore(snap); c.ivl=c.ivl_of(y); c.lane_cost=orig; c.prevrow={}
T=[__import__('cpp2').analysis(y[pi],5,c.Lvs[pi]) for pi in range(3)]
c.kst=[{kk:np.full(v.shape,60) for kk,v in T[pi].items()} for pi in range(3)]
kp=56
for k in range(c.nsl):
    r=orig(k,[k1[k]],T,None,kp,False,lambda pi,key,rows: np.ones((len(rows),T[pi][key].shape[1]),bool),c.kst)
    print('own chain slice',k,'exact at gen1 knot',bool(r[2][0])); kp=k1[k]
import cpp2
from cpp2 import Q,R
k=1; kp=k1[0]
for pi in range(3):
    for key,t in T[pi].items():
        sl,frac=c.band_slice_rows(pi,key,t.shape); rows=np.where(sl==k)[0]
        if not len(rows) or key=='LL': continue
        kap=np.round(kp+(k1[k]-kp)*np.minimum(frac[rows],1.0)).astype(int); D=c.D(pi,key,kap)[:,None]
        tt=t[rows]; ilo=c.ivl[pi][key][0][rows]; ihi=c.ivl[pi][key][1][rows]
        q0=Q(tt,D); ok=np.zeros(tt.shape,bool)
        for d in (0,-1,1): ok|=(np.clip(R(q0+d,D),ilo,ihi)==tt)
        if (~ok).any():
            j=np.where(~ok); print(pi,key,'fail',int((~ok).sum()),'t',tt[j][:3],'ilo',ilo[j][:3],'ihi',ihi[j][:3],'D',D.ravel()[:1])

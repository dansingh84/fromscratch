import os; os.environ['TABLES']='../out/tables_B.pkl'
import numpy as np, seq2, cpp2
from cpp2 import Q,R
tabs=seq2.Tables(); A='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/cut24.yuv'
W,H=256,64; B=0.5*W*8
c1=seq2.Codec(W,H,S=8,tabs=tabs); fr=seq2.read(A,W,H,0); y=c1.encode(fr,B); k1=c1.frame_info['kap']
c2=seq2.Codec(W,H,S=8,tabs=tabs); c2.excl=c2.excl_masks(y)
T=[cpp2.analysis(y[pi],5,c2.Lvs[pi]) for pi in range(3)]
c2.kst=[{k:np.full(v.shape,60) for k,v in T[pi].items()} for pi in range(3)]; c2.prevrow={}
print('gen1 kap',k1)
kp=56
for k in range(c2.nsl):
    for pi in range(3):
        for key,t in T[pi].items():
            sl,frac=c2.band_slice_rows(pi,key,t.shape); rows=np.where(sl==k)[0]
            if not len(rows) or key=='LL': continue
            kap=np.round(kp+(k1[k]-kp)*np.minimum(frac[rows],1.0)).astype(int)
            D=c2.D(pi,key,kap)[:,None]; tt=t[rows]; ex=c2.excl[pi][key][rows]
            ne=(R(Q(tt,D),D)!=tt)&~ex
            if ne.any(): print('slice',k,'pl',pi,key,'nonexact',int(ne.sum()),'of',tt.size,'excluded',int(ex.sum()),'t',tt[ne][:4],'D',D.ravel()[0].round(1))
    kp=k1[k]
c3=seq2.Codec(W,H,S=8,tabs=tabs)
orig=c3.lane_cost
def spy(k,cands,*a,**kw):
    r=orig(k,cands,*a,**kw)
    if len(cands)>3 and k<3: print('k',k,'kp',a[2],'exact at',[c for c,e in zip(cands,r[2]) if e], 'gen1',k1[k])
    return r
c3.lane_cost=spy
y3=c3.encode(y,B); print('gen2 kap',c3.frame_info['kap'])

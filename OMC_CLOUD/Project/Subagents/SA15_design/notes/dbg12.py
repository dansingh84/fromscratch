import os; os.environ['TABLES']='../out/tables_B.pkl'
import numpy as np, seq2, cpp2
from cpp2 import Q,R
A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv'; W,H=448,256
c=seq2.Codec(W,H,S=8,tabs=seq2.Tables())
f0=seq2.read(A,W,H,0); c.ivl=c.ivl_of(f0); c._encode(f0,0.5*W*8)
f1=seq2.read(A,W,H,1)
snap=c.snapshot(); c.ivl=c.ivl_of(f1); y=c._encode(f1,0.5*W*8); kap=list(c.frame_info['kap'])
c.restore(snap); c.ivl=c.ivl_of(y)
# rebuild MC exactly like _encode
V=c.frame_info['V'] if False else None
orig=c.lane_cost; seen={}
def spy(k,cands,T,Tm,kp,inter,hf,kst,want=False):
    r=orig(k,cands,T,Tm,kp,inter,hf,kst,want)
    if k==0 and len(cands)>3 and 'x' not in seen:
        seen['x']=1
        # per band exactness at gen-1 knot
        for pi in range(3):
            for key,t in T[pi].items():
                sl,frac=c.band_slice_rows(pi,key,t.shape); rows=np.where(sl==0)[0]
                kk=np.round(kp+(kap[0]-kp)*np.minimum(frac[rows],1.0)).astype(int); Df=c.D(pi,key,kk)[:,None]
                tt=t[rows]; ilo,ihi=c.ivl[pi][key][0][rows],c.ivl[pi][key][1][rows]
                Dp=np.minimum(c.D(pi,key,kst[pi][key][rows]),Df); tm=Tm[pi][key][rows]; vk=R(Q(tm,Dp),Dp)
                if key=='LL': continue
                q0=Q(tt,Df); ok=np.zeros(tt.shape,bool)
                for d in (0,-1,1): ok|=(np.clip(R(q0+d,Df),ilo,ihi)==tt)
                ok|=(np.clip(vk,ilo,ihi)==tt)
                if (~ok).any(): print('pl',pi,key,'nonexact',int((~ok).sum()),'t',tt[~ok][:3],'vk',vk[~ok][:3],'Df',Df.ravel()[:1],'Dp',Dp[~ok][:3])
    return r
c.lane_cost=spy
c._encode(y,0.5*W*8); print('gen1',kap[:4],'read',c.frame_info['kap'][:4])

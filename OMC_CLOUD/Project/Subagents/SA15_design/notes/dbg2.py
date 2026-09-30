import numpy as np, seq2, cpp2
from cpp2 import Q,R
tabs=seq2.Tables(); A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv'
fr=seq2.read(A,1280,720,0); B=0.5*1280*4
c1=seq2.Codec(1280,720,S=4,tabs=tabs); y=c1.encode(fr,B); k1=c1.frame_info['kap']; l1=c1.frame_info['lane']
c2=seq2.Codec(1280,720,S=4,tabs=tabs); y2=c2.encode(y,B); k2=c2.frame_info['kap']; l2=c2.frame_info['lane']
d=[k for k in range(len(k1)) if k1[k]!=k2[k]]
print('differ',len(d),'first',d[:5])
k=d[0]; print('k1',k1[k-1:k+2],'k2',k2[k-1:k+2],'lane1',l1[k],'lane2',l2[k])
# gen-2 lanes at slice k with kp=k1[k-1]
T=[cpp2.analysis(y[pi],5,c2.Lvs[pi]) for pi in range(3)]
c2.excl=c2.excl_masks(y)
kp=k1[k-1]; cands=sorted(set([k1[k],k2[k]]))
for pi in range(3):
    for key,t in T[pi].items():
        sl,frac=c2.band_slice_rows(pi,key,t.shape); rows=np.where(sl==k)[0]
        if not len(rows) or key=='LL': continue
        kap=np.round(kp+(k1[k]-kp)*np.minimum(frac[rows],1.0)).astype(int)
        D=c2.D(pi,key,kap)[:,None]; tt=t[rows]; ne=(R(Q(tt,D),D)!=tt)&~c2.excl[pi][key][rows]
        if ne.any(): print(pi,key,'nonexact',int(ne.sum()),tt[ne][:5],D.ravel()[:1])
def nexf(c,k): return sum(int(v[np.where(c.band_slice_rows(pi,key,v.shape)[0]==k)[0]].sum()) for pi in range(3) for key,v in c.excl[pi].items())
c1b=seq2.Codec(1280,720,S=4,tabs=tabs); c1b.excl=c1b.excl_masks(y)
print('nex gen2(input rails)',nexf(c1b,k),' gen1 pass-B rails(P_A)=?')
c2.kst=[{kk:np.full(v.shape,60) for kk,v in T[pi].items()} for pi in range(3)]; c2.prevrow={}
cost,ch,ex,U,last=c2.lane_cost(k,[61,69],T,None,kp,False,lambda *a:None,c2.kst,want=True)
print('gen2 lane cost',cost,'exact',ex)
# rails in the slice rows
print('rail samples in slice rows Y/Cb/Cr',[int(((y[pi][k*4:(k+1)*4]<=0)|(y[pi][k*4:(k+1)*4]>=1023)).sum()) for pi in range(3)],
      'source',[int(((fr[pi][k*4:(k+1)*4]<=0)|(fr[pi][k*4:(k+1)*4]>=1023)).sum()) for pi in range(3)])

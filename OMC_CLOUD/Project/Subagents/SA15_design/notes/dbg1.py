import numpy as np, seq2, cpp2
from cpp2 import Q,R
tabs=seq2.Tables(); A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv'
fr=seq2.read(A,1280,720,0); B=0.5*1280*4
c1=seq2.Codec(1280,720,S=4,tabs=tabs); y=c1.encode(fr,B); k1=c1.frame_info['kap']
c2=seq2.Codec(1280,720,S=4,tabs=tabs)
# instrument: run gen2 lanes slice by slice with gen1's kap to see exactness
T=[cpp2.analysis(y[pi],5,c2.Lvs[pi]) for pi in range(3)]
c2.kst=[{k:np.full(v.shape,60) for k,v in T[pi].items()} for pi in range(3)]; c2.prevrow={}
kp=56; bad=0
for k in range(c2.nsl):
    cands=[k1[k]]
    cost,ch,ex,U,last=c2.lane_cost(k,cands,T,None,kp,False,lambda *a:None,c2.kst,want=True)
    if not ex[0]:
        bad+=1
        if bad<=3:
            # find non-exact coefficients
            for pi in range(3):
                for key,t in T[pi].items():
                    sl,frac=c2.band_slice_rows(pi,key,t.shape); rows=np.where(sl==k)[0]
                    if not len(rows): continue
                    kap=np.round(kp+(k1[k]-kp)*np.minimum(frac[rows],1.0)).astype(int)
                    D=c2.D(pi,key,kap)[:,None]; tt=t[rows]
                    if key=='LL': continue
                    ne=(R(Q(tt,D),D)!=tt)
                    if ne.any(): print('slice',k,'plane',pi,key,'nonexact',int(ne.sum()),'examples t',tt[ne][:4],'D',D.ravel()[:2],'pix range',y[pi].min(),y[pi].max())
    for kk,v in last.items(): c2.prevrow[kk]=v[0]
    kp=k1[k]
print('slices not exact at gen-1 knot:',bad,'of',c2.nsl)

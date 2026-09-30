import numpy as np, seq2
tabs=seq2.Tables(); A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv'
B=0.5*1280*4; c=seq2.Codec(1280,720,S=4,tabs=tabs)
orig=c.lane_cost; rec=[]
def spy(k,cands,*a,**kw):
    r=orig(k,cands,*a,**kw)
    if len(cands)>3: rec.append((k,cands[-1],r[0][-1],r[1][-1],c.credit))
    return r
c.lane_cost=spy
for t in range(4):
    rec.clear(); ov=getattr(c,'overflow',0); c.encode(seq2.read(A,1280,720,t),B)
    bad=[x for x in rec if x[2]>x[4]-32]
    print(t,'overflow',c.overflow-ov,'first bad (k,kmax,cost@kmax,hf@kmax,credit):',[tuple(round(v) for v in x) for x in bad[:4]])

import numpy as np, seq2, cpp2
tabs=seq2.Tables(); A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv'
B=0.5*1280*4
c=seq2.Codec(1280,720,S=4,tabs=tabs)
f0=seq2.read(A,1280,720,0); c.encode(f0,B)
f1=seq2.read(A,1280,720,1)
# replicate lane call for slice 90 at frame 1
import types
orig=c.lane_cost
def spy(k,cands,*a,**kw):
    r=orig(k,cands,*a,**kw)
    if k==90 and len(cands)>3: print('slice',k,'kp',a[2],'cands',cands,'\n cost',np.round(r[0]).astype(int),'\n hf',np.round(r[1]).astype(int),'\n exact',r[2].astype(int))
    return r
c.lane_cost=spy
c.encode(f1,B); fi=c.frame_info
print('chosen',fi['lane'][90],'target-ish base',B*(1-c.rho))

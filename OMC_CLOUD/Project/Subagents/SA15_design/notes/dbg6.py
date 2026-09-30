import numpy as np, seq2
tabs=seq2.Tables(); A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv'
B=0.5*1280*4; c=seq2.Codec(1280,720,S=4,tabs=tabs)
orig=c.lane_cost; info={}
def spy(k,cands,*a,**kw):
    r=orig(k,cands,*a,**kw)
    if len(cands)>3: info[k]=(cands,r[0],r[1],r[2])
    return r
c.lane_cost=spy
for t in range(4):
    f=seq2.read(A,1280,720,t); ov0=getattr(c,"overflow",0); info.clear(); cr0=c.credit; y=c.encode(f,B)
    fi=c.frame_info
    print(t,'vbits',round(fi['vbits']),'overflows',c.overflow-ov0,'credit start',round(cr0))
    for k,l in enumerate(fi['lane']):
        if l[0]==110:
            ca,co,ch,ex=info[k]; print('  slice',k,'lane',[round(x) for x in l],'cost@kmax',round(co[-1]),'hf@kmax',round(ch[-1]),'min cost',round(co.min()),'exact any',ex.any()); break

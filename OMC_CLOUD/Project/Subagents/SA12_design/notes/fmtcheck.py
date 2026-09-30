import sys, math, numpy as np
sys.argv=['x']; import hf
A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
for path,W,H,fmt,depth,lo,hi,tag in ((A+'dng_1920x1080_444_12.yuv',1920,1080,'444',12,0,4095,'444/12 full'),
                                     (A+'dng_1920x1080_422_8.yuv',1920,1080,'422',8,1,254,'422/8 SDI-legal 1..254'),
                                     (A+'dng_1280x720_422_10.yuv',1280,720,'422',10,64,940,'422/10 limited 64..940 (source clamped)')):
    P=hf.load(path,W,H,5,fmt); sh=16 if H>720 else 8
    for Qf in (depth-10+4.0, depth-10+7.0):
        res=[]
        for pi,p in enumerate(P):
            p=np.clip(p,lo,hi)
            b,ps,oor,rt0,g2,ph,ncl=hf.code_plane(p,sh,5,3,'s10','s10a',True,Qf,-1,lo,hi,depth,{})
            res.append((oor,rt0,g2,ncl))
        print(tag,'Qf',Qf,'per plane (out-of-range, decoder==encoder, gen2 exact, clamp-site index changes):',res,flush=True)

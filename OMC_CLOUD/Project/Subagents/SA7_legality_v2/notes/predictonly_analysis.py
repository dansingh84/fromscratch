#!/usr/bin/env python3
"""[SA7] DESIGN3 (d): source-only comparison of the SHIPPED tree (5/3 vertical + (9,7)-M horizontal
at levels 1-2, 5/3 at 3-5, predict AND update) against the PREDICT-ONLY tree (same predicts, no
update; lowpass = the even samples).  Reports per-band energy and a coding-gain proxy.
No codec, no build."""
import sys, numpy as np
src,W,H,f = sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4])
Wc=W//2; fw=W*H+2*Wc*H
Y=np.fromfile(src,dtype=np.uint16)[f*fw:f*fw+W*H].astype(np.int64).reshape(H,W)
Y=Y-512  # centre roughly; only differences matter

def split53(x, axis, update):
    x=np.moveaxis(x,axis,0); n=x.shape[0]//2*2; x=x[:n]
    e=x[0::2].copy(); o=x[1::2].copy()
    e1=np.concatenate([e[1:], e[-1:]],0)
    d=o-((e+e1)//2)
    if update:
        dm=np.concatenate([d[:1], d[:-1]],0)
        s=e+((dm+d+2)//4)
    else:
        s=e
    return np.moveaxis(s,0,axis), np.moveaxis(d,0,axis)

def split97(x, axis, update):
    x=np.moveaxis(x,axis,0); n=x.shape[0]//2*2; x=x[:n]
    e=x[0::2].copy(); o=x[1::2].copy()
    a=np.concatenate([e[1:2], e[:-1]],0)          # s_{i-1}, symmetric
    c=np.concatenate([e[1:], e[-1:]],0)           # s_{i+1}
    dd=np.concatenate([e[2:], e[-1:], e[-2:-1]],0)# s_{i+2}
    d=o-((9*(e+c)-(a+dd)+8)//16)
    if update:
        dm=np.concatenate([d[:1], d[:-1]],0)
        s=e+((dm+d+2)//4)
    else:
        s=e
    return np.moveaxis(s,0,axis), np.moveaxis(d,0,axis)

def tree(x, update):
    """anisotropic: V1, H1(97), V2, H2(97), H3, H4, H5 (5/3)"""
    bands={}
    s,d = split53(x,0,update); bands['LH1']=d
    s,d2 = split97(s,1,update); bands['HL1']=d2
    # HH1 = horizontal split of the vertical highpass
    _,hh = split97(bands['LH1'],1,update); bands['HH1']=hh
    s2,d3 = split53(s,0,update); bands['LH2']=d3
    s3,d4 = split97(s2,1,update); bands['HL2']=d4
    _,hh2 = split97(d3,1,update); bands['HH2']=hh2
    for name in ('HL3','HL4','HL5'):
        s3,dn = split53(s3,1,update); bands[name]=dn
    bands['LL5']=s3
    return bands

def report(tag, b):
    tot=0; parts=[]
    for k in ('LL5','HL5','HL4','HL3','LH2','HL2','HH2','LH1','HL1','HH1'):
        v=b[k].astype(float); e=(v*v).mean(); n=v.size
        parts.append((k,e,n)); tot+=e*n
    print("  %-12s"%tag, " ".join("%s %.0f"%(k,e) for k,e,_ in parts))
    # coding-gain proxy: arithmetic / geometric mean of subband variances, weighted by size
    N=sum(n for _,_,n in parts)
    am=sum(e*n for _,e,n in parts)/N
    gm=np.exp(sum(n*np.log(max(e,1e-9)) for _,e,n in parts)/N)
    print("               AM/GM coding gain proxy = %.2f dB" % (10*np.log10(am/gm)))
    return am/gm

print("=== %s frame %d ===" % (src.split('/')[-1], f))
g1=report("with update", tree(Y, True))
g0=report("PREDICT-ONLY", tree(Y, False))
print("  predict-only loses %.2f dB of coding gain" % (10*np.log10(g1/g0)))

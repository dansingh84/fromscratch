#!/usr/bin/env python3
"""pulse.py — the PULSATION vs CRAWL vs FIXED classifier, source-referenced.

Owner requirement (2026-08-31): a crawl fix must not turn per-frame shimmer into
periodic pixel-group changes every second or two (pulsation).  Frame-pair diffs of
the decode cannot see this — the reference is ALWAYS THE SOURCE (the sect.51.15
rule): per 16x16 block, per frame, the block's error field vs source is tracked as
a time series, and each block is classified:

  fixed     : error settles and stays (low churn, no steps)
  crawl     : error pattern decorrelates frame after frame (high churn rate)
  pulsation : error holds still for stretches, then JUMPS and holds again
              (rare large envelope steps); dominant step period reported

Churn of a block at t = 1 - corr(err_t, err_t-1) over the block's pixels (0 = the
error field froze, 1 = fully redrawn), counted when the block has meaningful error
(rms > 1 code).  A step = frame where churn > 0.5 (the field visibly re-drew).
Blocks stepping on >=25% of frames = crawl; blocks with 1..(nf/8) steps = pulsing;
blocks with 0 steps = fixed.  Period = median gap between steps of pulsing blocks.

  pulse.py SRC.yuv DEC.yuv W H NF [--fmt 422] [--depth 10] [--blk 16]
"""
import sys, numpy as np
sys.path.insert(0,'v53/omc_v5.3/harness'); import yuvio
a=sys.argv[1:]
src,dec,W,H,NF=a[0],a[1],int(a[2]),int(a[3]),int(a[4])
fmt,depth,blk='422',10,16
i=5
while i<len(a):
    if a[i]=='--fmt': fmt=a[i+1]; i+=2
    elif a[i]=='--depth': depth=int(a[i+1]); i+=2
    elif a[i]=='--blk': blk=int(a[i+1]); i+=2
    else: i+=1
sc=1<<(depth-10)
for pi,pname in ((0,'Y'),(1,'Cb'),(2,'Cr')):
    errs=[]
    for f in range(NF):
        ps=yuvio.planes(src,W,H,f,fmt,depth)[pi].astype(np.float64)
        pd=yuvio.planes(dec,W,H,f,fmt,depth)[pi].astype(np.float64)
        errs.append((pd-ps)/sc)
    h,w=errs[0].shape; nh,nw=h//blk,w//blk
    E=np.array([e[:nh*blk,:nw*blk].reshape(nh,blk,nw,blk).transpose(0,2,1,3).reshape(nh,nw,-1) for e in errs])
    rms=np.sqrt((E**2).mean(-1))                      # (NF,nh,nw)
    Ec=E-E.mean(-1,keepdims=True)
    num=(Ec[1:]*Ec[:-1]).sum(-1)
    den=np.sqrt((Ec[1:]**2).sum(-1)*(Ec[:-1]**2).sum(-1))+1e-9
    churn=1-num/den                                    # (NF-1,nh,nw)
    active=(rms[1:]>1.0)&(rms[:-1]>1.0)
    step=(churn>0.5)&active
    nstep=step.sum(0); nact=active.sum(0)
    fixedb=crawlb=pulseb=0; periods=[]
    for y in range(nh):
        for x in range(nw):
            if nact[y,x] < NF//4: continue            # block never meaningfully wrong
            ns=nstep[y,x]
            if ns==0: fixedb+=1
            elif ns>=0.25*nact[y,x]: crawlb+=1
            else:
                pulseb+=1
                ts=np.nonzero(step[:,y,x])[0]
                if len(ts)>1: periods.extend(np.diff(ts).tolist())
                elif len(ts)==1: periods.append(NF)   # single jump in the run
    per=(f" period~{int(np.median(periods))}f" if periods else "")
    tot=max(fixedb+crawlb+pulseb,1)
    print(f"PULSE {pname}: active-blocks {fixedb+crawlb+pulseb}  fixed {fixedb} ({100*fixedb//tot}%)  crawl {crawlb} ({100*crawlb//tot}%)  pulsing {pulseb} ({100*pulseb//tot}%){per}")

# CPP-LL v2 plane codec (round 2).
# - Open-loop symbols: q is quantised from the source's own TS coefficients (source predictors), so the
#   bits of any candidate step are computable before coding (exact rate lanes); the decoder offsets are the
#   reconstructed predictors, and a decoded picture re-analysed gives back exactly its own values (exactness).
# - Per-coefficient step memory: a coefficient whose MC hint reproduces it keeps the step it was coded with,
#   so rate adaptation (the knot field) never touches still content.
# - Canonical classification in the decode loop (keep / lattice index incl. clamped boundary values).
import numpy as np
fl=np.floor_divide
PR=[(-1,16),(1,-16)]
def sh(a,k,axis):
    n=a.shape[axis]; idx=np.clip(np.arange(n)+k,0,n-1); return np.take(a,idx,axis=axis)
def pred(m,axis):
    acc=np.zeros_like(m)
    for k,w in PR: acc+=w*sh(m,k,axis)
    return fl(acc+32,64)
def rpat(shape):
    i=np.arange(shape[0])[:,None]; j=np.arange(shape[1])[None,:]; return ((i+j)&1).astype(np.int64)
def raxis(shape,axis):
    s=list(shape); s[0],s[axis]=s[axis],s[0]; return np.moveaxis(rpat(tuple(s)),0,axis)
def split(x,axis):
    t=np.moveaxis(x,axis,0); e=t[0::2]; o=t[1::2]; r=rpat(e.shape)
    return np.moveaxis(fl(e+o+r,2),0,axis),np.moveaxis(e-o,0,axis)
def merge(m,d,axis):
    m=np.moveaxis(m,axis,0); d=np.moveaxis(d,axis,0); r=rpat(m.shape)
    s=2*m+((d+r)&1)-r; e=(s+d)//2; o=(s-d)//2
    x=np.empty((2*m.shape[0],)+m.shape[1:],dtype=np.int64); x[0::2]=e; x[1::2]=o
    return np.moveaxis(x,0,axis)
def dbox(A0,A1,B0,B1,m,r):
    lo0=np.maximum(2*(A0-m)-1,2*(m-B1)); hi0=np.minimum(2*(A1-m),2*(m-B0)+1)
    lo1=np.maximum(2*(A0-m),2*(m-B1)-1); hi1=np.minimum(2*(A1-m)+1,2*(m-B0))
    return np.where(r==1,lo1,lo0), np.where(r==1,hi1,hi0)
def sbox(b0,b1,axis):
    t0=np.moveaxis(b0,axis,0); t1=np.moveaxis(b1,axis,0)
    return [np.moveaxis(t,0,axis) for t in (t0[0::2],t1[0::2],t0[1::2],t1[1::2])]
DZ=0.45
def Q(x,D): return (np.sign(x)*np.floor(np.abs(x)/D+DZ)).astype(np.int64)
def R(q,D): return np.round(q*D).astype(np.int64)
# ---------------- analysis (open loop, source predictors) ----------------
def analysis(x,Lh,Lv):
    T={}; ll=x
    for k in range(Lh):
        if k<Lv:
            Lv_,Dv=split(ll,0); LL,LH=split(Lv_,1)
            T[('LH',k)]=LH-pred(LL,1)
            Dvp=Dv-pred(Lv_,0); HL,HH=split(Dvp,1)
            T[('HL',k)]=HL; T[('HH',k)]=HH-pred(HL,1); ll=LL
        else:
            LL,H=split(ll,1); T[('H',k)]=H-pred(LL,1); ll=LL
    T['LL']=ll
    return T
def keys(Lh,Lv):
    out=['LL']
    for k in range(Lh-1,-1,-1):
        out+= [('H',k)] if k>=Lv else [('LH',k),('HL',k),('HH',k)]
    return out
def rowsp(key,Lv):
    if key=='LL' or key[0]=='H': return 1<<Lv
    return 1<<(key[1]+1)
# ---------------- per-quantity choice + canonical classification ----------------
def choose_cls(t,tmc,Df,Dp,ilo,ihi,inter,theta,enc,sym=None,hintfree=None,decstate=None):
    """t-domain. ilo/ihi = legal interval of the value (t-domain). Returns w (final value), q (canonical at its
    step), kept (bool), Dnew (state), symbols (dict). enc: choose from t; dec: from sym."""
    clampI=lambda v: np.clip(v,ilo,ihi)
    if inter is None: inter=np.zeros(ilo.shape,bool)
    if Dp is None: Dp=np.broadcast_to(Df,ilo.shape)
    Dp=np.minimum(Dp,Df)          # memory step never coarser than the field: refinement re-rounds, coarsening keeps
    tm=tmc if tmc is not None else np.zeros(ilo.shape,np.int64)
    vkeep=R(Q(tm,Dp),Dp); hk=Q(tm,Df)
    Dfb=np.broadcast_to(Df,ilo.shape)
    if enc:
        ck=clampI(vkeep)
        q0=Q(t,Dfb)
        # exact reproduction first (decoded input), smallest |q| that reproduces t
        ex=np.zeros(ilo.shape,bool); qex=q0.copy()
        for dq_ in (0,-1,1):
            qq=q0+dq_; hit=(clampI(R(qq,Dfb))==t)&~ex; qex=np.where(hit,qq,qex); ex|=hit
        exk=inter&(ck==t)
        hyk=inter&((np.abs(t-vkeep)<=(0.5+theta)*Dp)|(np.abs(t-vkeep)<=np.abs(t-R(q0,Dfb))))
        keepc=exk|(~ex&hyk)
        u=np.where(keepc,vkeep,np.where(ex,R(qex,Dfb),R(q0,Dfb)))
    else:
        keepc=inter&(sym==0)&~hintfree
        s=sym; s=np.where(s>0,s-1,s)            # undo keep-skip mapping
        qd=np.where(hintfree,sym,s+hk)
        # hint-free kept coefficients carry their own step via Dp state restored by refresh map
        u=np.where(keepc,vkeep,R(qd,np.where(hintfree&decstate,Dp,Dfb)))
    w=clampI(u)
    if enc: kept=inter&(w==clampI(vkeep))
    else: kept=inter&np.where(hintfree,decstate,sym==0)
    # canonical index at Df (non-kept) or Dp (kept, for hint-free symbols)
    def canon(w,D):
        """smallest |q| whose clamped reconstruction equals w (unique lattice index inside the interval;
        a half-line of indices on a boundary)"""
        q=Q(w,D)
        top=(w==ihi); bot=(w==ilo)
        qu=np.ceil(w/D-1e-9).astype(np.int64); qu=np.where(R(qu,D)<w,qu+1,qu); qu=np.where(R(qu-1,D)>=w,qu-1,qu)
        qd=np.floor(w/D+1e-9).astype(np.int64); qd=np.where(R(qd,D)>w,qd-1,qd); qd=np.where(R(qd+1,D)<=w,qd+1,qd)
        ct=np.where(ihi<=0,0,qu); cb=np.where(ilo>=0,0,qd)
        both=top&bot
        qa=np.where(top,ct,q); qa=np.where(bot,cb,qa)
        qa=np.where(both,0,qa)
        qa=np.where(top&bot,0,qa)
        # top&bot aside, a boundary value may also be an exact lattice point with smaller |q|: take the smaller
        qa=np.where(top&~bot&(np.abs(q)<np.abs(qa))&(clampI(R(q,D))==w),q,qa)
        qa=np.where(bot&~top&(np.abs(q)<np.abs(qa))&(clampI(R(q,D))==w),q,qa)
        return qa
    Dpb=np.broadcast_to(Dp,ilo.shape)
    qc=canon(w,Dfb); qk=canon(w,Dpb)
    Dnew=np.where(kept,Dpb,Dfb)
    symP=np.where(kept,0,np.where(qc-hk>=0,qc-hk+1,qc-hk))     # hinted symbol (0 = keep)
    symI=np.where(kept,qk,qc)                                     # hint-free symbol (+ keep flag in refresh)
    return w,kept,Dnew,symP,symI
# ---------------- plane coder (full frame, synthesis order) ----------------
def code_plane(T,Tmc,Df,Dp,lo,hi,Lh,Lv,inter,hintfree,theta=0.25,enc=True,SYM=None,decstate=None,mid=None):
    """T: source analysis (enc) ; Tmc: MC analysis or None ; Df/Dp: dict key -> step arrays (Df rows x 1,
    Dp full); inter/hintfree: dict key -> bool arrays (inter = hint available & allowed; hintfree = send q).
    Returns picture, out dict key -> (kept, Dnew, symP, symI, used-symbol, w)."""
    out={}
    def do(key,t,ilo,ihi,poff):
        tm=None if Tmc is None else Tmc[key]
        it=None if Tmc is None else inter[key]
        hf=hintfree[key] if hintfree is not None else np.ones(ilo.shape,bool)
        if enc:
            w,kept,Dn,sP,sI=choose_cls(t-0,tm,Df[key],None if Dp is None else Dp[key],ilo,ihi,it,theta,True)
        else:
            w,kept,Dn,sP,sI=choose_cls(None,tm,Df[key],None if Dp is None else Dp[key],ilo,ihi,it,theta,False,
                                       sym=SYM[key],hintfree=hf,decstate=decstate[key] if decstate else np.zeros(ilo.shape,bool))
        used=np.where(hf,sI,sP)
        out[key]=(kept,Dn,sP,sI,used,w,hf)
        return w+poff
    # LL: DPCM from left decoded LL (col 0: mid), hinted when inter
    sh_=T['LL'].shape if enc else SYM['LL'].shape
    llr=np.zeros(sh_,np.int64); mid=(lo+hi+1)//2 if mid is None else mid
    cols=[]
    for c in range(sh_[1]):
        p=np.full(sh_[0],mid,np.int64) if c==0 else llr[:,c-1]
        sub=lambda a: None if a is None else a[:,c:c+1]
        key='LL'
        tm=None if Tmc is None else (Tmc['LL'][:,c:c+1]-p[:,None])   # MC LL expressed against the same predictor
        it=None if Tmc is None else inter['LL'][:,c:c+1]
        hf=hintfree['LL'][:,c:c+1] if hintfree is not None else np.ones((sh_[0],1),bool)
        ilo=(lo-p)[:,None]; ihi=(hi-p)[:,None]
        Dpc=None if Dp is None else Dp['LL'][:,c:c+1]
        if enc:
            w,kept,Dn,sP,sI=choose_cls(T['LL'][:,c:c+1]-p[:,None],tm,Df['LL'],Dpc,ilo,ihi,it,theta,True)
        else:
            w,kept,Dn,sP,sI=choose_cls(None,tm,Df['LL'],Dpc,ilo,ihi,it,theta,False,sym=SYM['LL'][:,c:c+1],hintfree=hf,
                                       decstate=decstate['LL'][:,c:c+1] if decstate else np.zeros((sh_[0],1),bool))
        llr[:,c]=(w[:,0]+p)
        cols.append((kept,Dn,sP,sI,np.where(hf,sI,sP),w,hf))
    out['LL']=tuple(np.concatenate([c[i] for c in cols],1) for i in range(7))
    for k in range(Lh-1,-1,-1):
        if k>=Lv:
            key=('H',k); m=llr; ps=pred(m,1); r=raxis(m.shape,1)
            A0=np.full(m.shape,lo); A1=np.full(m.shape,hi); dlo,dhi=dbox(A0,A1,A0,A1,m,r)
            d=do(key,T[key] if enc else None,dlo-ps,dhi-ps,ps)
            llr=merge(m,d,1)
        else:
            key=('LH',k); m=llr; ps=pred(m,1); r=raxis(m.shape,1)
            A0=np.full(m.shape,lo); A1=np.full(m.shape,hi); dlo,dhi=dbox(A0,A1,A0,A1,m,r)
            d=do(key,T[key] if enc else None,dlo-ps,dhi-ps,ps)
            Lvr=merge(m,d,1)
            pv=pred(Lvr,0); F=np.full(Lvr.shape,lo); G=np.full(Lvr.shape,hi)
            vlo,vhi=dbox(F,G,F,G,Lvr,raxis(Lvr.shape,0))
            A0,A1,B0,B1=sbox(vlo-pv,vhi-pv,1); rr=raxis(A0.shape,1)
            mlo=fl(A0+B0+rr,2); mhi=fl(A1+B1+rr,2)
            key=('HL',k); mh=do(key,T[key] if enc else None,mlo,mhi,0)
            key=('HH',k); ps=pred(mh,1); dlo,dhi=dbox(A0,A1,B0,B1,mh,rr)
            dh=do(key,T[key] if enc else None,dlo-ps,dhi-ps,ps)
            llr=merge(Lvr,merge(mh,dh,1)+pv,0)
    return llr,out

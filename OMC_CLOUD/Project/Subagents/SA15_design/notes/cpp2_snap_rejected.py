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
SNAP=0.6
def choose_cls(t,tmc,Df,Dp,ilo,ihi,inter,theta,enc,sym=None,hintfree=None,decstate=None):
    """t-domain. Reconstruction alphabet = lattice R(q) clamped into [ilo,ihi], with the boundary SNAP zone:
    a reconstruction within SNAP*D of a boundary IS the boundary (so every boundary value is the dead-zone
    index's own reconstruction: exact re-encoding needs no extra index)."""
    if inter is None: inter=np.zeros(ilo.shape,bool)
    if Dp is None: Dp=np.broadcast_to(Df,ilo.shape)
    Dp=np.minimum(Dp,Df)
    tm=tmc if tmc is not None else np.zeros(ilo.shape,np.int64)
    Dfb=np.broadcast_to(Df,ilo.shape); Dpb=np.broadcast_to(Dp,ilo.shape)
    def rec(q,D):
        v=np.clip(R(q,D),ilo,ihi); dt=ihi-v; db=v-ilo
        return np.where((dt<=SNAP*D)&(dt<=db),ihi,np.where(db<=SNAP*D,ilo,v))
    vkeep=rec(Q(tm,Dpb),Dpb); hk=Q(tm,Dfb)
    if enc:
        q0=Q(t,Dfb); v0=rec(q0,Dfb)
        ex=(v0==t); qex=q0.copy()
        for dq_ in (-1,1):
            qq=q0+dq_; hit=(rec(qq,Dfb)==t)&~ex; qex=np.where(hit,qq,qex); ex|=hit
        # snap-aware nearest: a snapped reconstruction may be replaced by the next index toward zero
        qz=q0-np.sign(q0); vz=rec(qz,Dfb)
        qn=np.where((v0!=np.clip(R(q0,Dfb),ilo,ihi))&(np.abs(vz-t)<np.abs(v0-t)),qz,q0)
        exk=inter&(vkeep==t)
        vn=rec(qn,Dfb)
        hyk=inter&((np.abs(t-vkeep)<=(0.5+theta)*Dpb)|(np.abs(t-vkeep)<=np.abs(t-vn)))
        keepc=exk|(~ex&hyk)
        w=np.where(keepc,vkeep,np.where(ex,rec(qex,Dfb),vn))
    else:
        keepc=inter&(sym==0)&~hintfree
        s=np.where(sym>0,sym-1,sym)
        qd=np.where(hintfree,sym,s+hk)
        Du=np.where(hintfree&decstate,Dpb,Dfb)
        w=np.where(keepc,vkeep,rec(qd,Du))
    if enc: kept=inter&(w==vkeep)
    else: kept=inter&np.where(hintfree,decstate,sym==0)
    def canon(w,D):
        q=Q(w,D)
        qt=np.ceil((ihi-SNAP*D)/D-1e-9).astype(np.int64)
        qb=np.floor((ilo+SNAP*D)/D+1e-9).astype(np.int64)
        best=np.full(w.shape,10**9,np.int64)
        for c in (np.zeros_like(q),q,q-1,q+1,qt,qt-1,qt+1,qb,qb-1,qb+1):
            hit=(rec(c,D)==w)&(np.abs(c)<np.abs(best)); best=np.where(hit,c,best)
        return np.where(best==10**9,q,best)
    qc=canon(w,Dfb); qk=canon(w,Dpb)
    Dnew=np.where(kept,Dpb,Dfb)
    symP=np.where(kept,0,np.where(qc-hk>=0,qc-hk+1,qc-hk))
    symI=np.where(kept,qk,qc)
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

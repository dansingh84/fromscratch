# CPP plane codec: continuous pair pyramid (2/6 TS form), legal boxes, canonical indices,
# in-band temporal prediction with hybrid predictor, per-coefficient intra mask (refresh zones).
import numpy as np
from tsx import fl, sh, pred, ipair, Qi, Rv, canon, dq, choose, srcpairs
KIND='26'; KV='26'
def pairsplit(x,axis):
    L,d=srcpairs(x,axis); return L,d
def box_proj(A0,A1,B0,B1): return fl(A0+B0,2), fl(A1+B1,2)
def split_boxes(box0,box1,axis):
    t0=np.moveaxis(box0,axis,0); t1=np.moveaxis(box1,axis,0)
    A0,A1,B0,B1=t0[0::2],t1[0::2],t0[1::2],t1[1::2]
    return [np.moveaxis(t,0,axis) for t in (A0,A1,B0,B1)]
def dbox(A0,A1,B0,B1,m): return np.maximum(2*(A0-m)-1,2*(m-B1)), np.minimum(2*(A1-m),2*(m-B0)+1)
class Coder:
    """Codes one quantity array: value v = clamp(R(q)+p, [lo,hi]); canonical q.
    Index-domain mode: p is the INTRA predictor everywhere; for inter coefficients a hint index h
    (the canonical index the MC value would get) is subtracted before entropy coding: stored r=q-h."""
    def __init__(s,enc,idx,D,theta=0.25): s.enc=enc; s.idx=idx; s.D=D; s.theta=theta
    def do(s,key,t,p,lo,hi,tmc=None,inter=None):
        D=s.D[key]
        if tmc is None:
            if s.enc:
                v=choose(t-p,p,lo,hi,D); q=canon(v,p,lo,hi,D); s.idx[key]=q
            else: q=s.idx[key]
            return dq(q,p,lo,hi,D)
        h=canon(choose(tmc-p,p,lo,hi,D),p,lo,hi,D); h=np.where(inter,h,0)
        if s.enc:
            v=choose(t-p,p,lo,hi,D); q=canon(v,p,lo,hi,D)
            exact=(dq(q,p,lo,hi,D)==t)
            vh=dq(h,p,lo,hi,D)
            keep=inter&(~exact)&(np.abs(t-vh)<=(0.5+s.theta)*D)
            q=np.where(keep,h,q); s.idx[key]=q-h
        else: q=s.idx[key]+h
        return dq(q,p,lo,hi,D)
def mc_pyr(mc,Lh,Lv):
    """plain analysis of the MC image (raw pairs, its own predictors)"""
    out=[]; ll=mc
    for k in range(Lh):
        if k<Lv:
            Lv_,Dv=pairsplit(ll,0); LL,LH=pairsplit(Lv_,1)
            Dvp=Dv-pred(Lv_,0,KV); HL,HH=pairsplit(Dvp,1)
            out.append(dict(Lv=Lv_,Dv=Dv,LL=LL,LH=LH,HL=HL,HH=HH)); ll=LL
        else:
            LL,H=pairsplit(ll,1); out.append(dict(LL=LL,H=H)); ll=LL
    return out,ll
def code_plane(x,D,Lh,Lv,lo,hi,mc=None,imask=None,enc=True,idx=None,tmode='val',theta=0.25):
    """x: target image (enc). mc: MC prediction image or None (all intra).
    imask(key,shape)-> bool array True where the coefficient is INTRA (refresh / intra frame).
    Returns recon, idx."""
    if idx is None: idx={}
    C=Coder(enc,idx,D,theta)
    IDX=(tmode=='idx') and (mc is not None)
    if enc:
        src=[]; ll=x
        for k in range(Lh):
            if k<Lv:
                Lv_,Dv=pairsplit(ll,0); LL,LH=pairsplit(Lv_,1); src.append(dict(Lv=Lv_,Dv=Dv,LH=LH)); ll=LL
            else:
                LL,H=pairsplit(ll,1); src.append(dict(H=H)); ll=LL
        tLL=ll
    if mc is not None: mp,mLL=mc_pyr(mc,Lh,Lv)
    def im(key,shape):
        if mc is None: return np.ones(shape,bool)
        return imask(key,shape)
    # coarsest LL: intra DPCM-left (col 0 from mid), inter p = mLL
    shp=idx['LL'].shape if not enc else tLL.shape
    I=im('LL',shp); rec=np.zeros(shp,dtype=np.int64); mid=(lo+hi+1)//2
    if enc: qLL=np.zeros(shp,dtype=np.int64)
    else: qLL=idx['LL']
    Dl=D['LL']
    for c in range(shp[1]):
        p_intra=np.full(shp[0],mid,dtype=np.int64) if c==0 else rec[:,c-1]
        if IDX:
            sub={'LL':qLL[:,c]} if not enc else {}
            Cc=Coder(enc,sub,{'LL':Dl},theta)
            rec[:,c]=Cc.do('LL',tLL[:,c] if enc else None,p_intra,lo,hi,tmc=mLL[:,c],inter=~I[:,c])
            if enc: qLL[:,c]=sub['LL']
            continue
        p=np.where(I[:,c],p_intra,mLL[:,c] if mc is not None else p_intra)
        if enc:
            v=choose(tLL[:,c]-p,p,lo,hi,Dl); qLL[:,c]=canon(v,p,lo,hi,Dl)
        rec[:,c]=dq(qLL[:,c],p,lo,hi,Dl)
    idx['LL']=qLL; llr=rec
    for k in range(Lh-1,-1,-1):
        W2=2*llr.shape[1]
        if k>=Lv:
            key=('H',k); m=llr; ps=pred(m,1,KIND)
            A0=np.full(m.shape,lo); A1=np.full(m.shape,hi)
            dlo,dhi=dbox(A0,A1,A0,A1,m)
            I=im(key,m.shape)
            if IDX: d=C.do(key,src[k]['H'] if enc else None,ps,dlo,dhi,tmc=mp[k]['H'],inter=~I)
            else:
                p=ps if mc is None else np.where(I,ps,mp[k]['H']+ps-pred(mp[k]['LL'],1,KIND))
                d=C.do(key,src[k]['H'] if enc else None,p,dlo,dhi)
            llr=ipair(m,d,1)
        else:
            # L_v rows = horizontal pairs from (LL=llr, LH)
            key=('LH',k); m=llr; ps=pred(m,1,KIND)
            A0=np.full(m.shape,lo); A1=np.full(m.shape,hi); dlo,dhi=dbox(A0,A1,A0,A1,m)
            I=im(key,m.shape)
            if IDX: d=C.do(key,src[k]['LH'] if enc else None,ps,dlo,dhi,tmc=mp[k]['LH'],inter=~I)
            else:
                p=ps if mc is None else np.where(I,ps,mp[k]['LH']+ps-pred(mp[k]['LL'],1,KIND))
                d=C.do(key,src[k]['LH'] if enc else None,p,dlo,dhi)
            Lvr=ipair(m,d,1)
            # vertical diffs: boxes from Lvr
            pv=pred(Lvr,0,KV); vlo,vhi=dbox(np.full(Lvr.shape,lo),np.full(Lvr.shape,hi),np.full(Lvr.shape,lo),np.full(Lvr.shape,hi),Lvr)
            b0=vlo-pv; b1=vhi-pv    # boxes on D_v' samples
            A0,A1,B0,B1=split_boxes(b0,b1,1); mlo,mhi=box_proj(A0,A1,B0,B1)
            if enc:
                Dvp=src[k]['Dv']-pv; tHL,tHH=pairsplit(Dvp,1)
            key=('HL',k); I=im(key,mlo.shape)
            if IDX:
                mHL,mHH=pairsplit(mp[k]['Dv']-pv,1)
                mh=C.do(key,tHL if enc else None,np.zeros_like(mlo),mlo,mhi,tmc=mHL,inter=~I)
            else:
                p=np.zeros_like(mlo) if mc is None else np.where(I,0,mp[k]['HL'])
                mh=C.do(key,tHL if enc else None,p,mlo,mhi)
            key=('HH',k); ps=pred(mh,1,KIND); dlo,dhi=dbox(A0,A1,B0,B1,mh); I=im(key,mh.shape)
            if IDX: dh=C.do(key,tHH if enc else None,ps,dlo,dhi,tmc=mHH,inter=~I)
            else:
                p=ps if mc is None else np.where(I,ps,mp[k]['HH']+ps-pred(mp[k]['HL'],1,KIND))
                dh=C.do(key,tHH if enc else None,p,dlo,dhi)
            Dvpr=ipair(mh,dh,1)
            llr=ipair(Lvr,Dvpr+pv,0)
    return llr,idx
def band_rows(key,shape,Lv,H):
    """plane-row index (top row covered) and row span of each coefficient row of the band"""
    k=key[1] if isinstance(key,tuple) else None
    if key=='LL' or key[0]=='H': sp=1<<Lv
    elif key[0]=='LH': sp=1<<(k+1)   # rows of L_v at level k: spacing 2^(k+1)
    else: sp=1<<(k+1)                 # HL/HH rows = vertical pairs at level k
    return np.arange(shape[0])*sp, sp

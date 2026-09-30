# TS-family (Haar pair + predicted difference) separable transform with decoder-side legal
# interval clamps (box projection), canonical indices, full-frame continuous (no slices).
import numpy as np
fl=np.floor_divide
def sh(a,k,axis):
    """a shifted so that out[i]=a[i+k] with edge replication along axis"""
    n=a.shape[axis]; idx=np.clip(np.arange(n)+k,0,n-1); return np.take(a,idx,axis=axis)
PRED={'26c':[(-1,32),(0,-32)],'26':[(-1,16),(1,-16)],'210':[(-2,-3),(-1,22),(1,-22),(2,3)],'0':[]}
def pred(L,axis,kind):
    if not PRED[kind]: return np.zeros_like(L)
    acc=np.zeros_like(L)
    for k,w in PRED[kind]: acc+=w*sh(L,k,axis)
    return fl(acc+32,64)
def fpair(x,axis,kind):
    x=np.moveaxis(x,axis,0); e=x[0::2]; o=x[1::2]
    L=fl(e+o,2); d=e-o
    L=np.moveaxis(L,0,axis); d=np.moveaxis(d,0,axis)
    return L, d-pred(L,axis,kind)
def ipair(L,d,axis):
    L=np.moveaxis(L,axis,0); d=np.moveaxis(d,axis,0)
    e=L+fl(d+1,2); o=e-d
    x=np.empty((2*L.shape[0],)+L.shape[1:],dtype=np.int64); x[0::2]=e; x[1::2]=o
    return np.moveaxis(x,0,axis)
def fwd(x,Lh,Lv,kv,kh):
    bands=[]; ll=x
    for k in range(Lh):
        if k<Lv:
            Lv_,Dv=fpair(ll,0,kv); LL,LH=fpair(Lv_,1,kh); HL,HH=fpair(Dv,1,kh)
            bands.append(('2d',LH,HL,HH)); ll=LL
        else:
            LL,H=fpair(ll,1,kh); bands.append(('1d',H)); ll=LL
    return ll,bands
# ---- quantiser (canonical) ----
import os
DZO=float(os.environ.get('DZ','0.3333333333'))
def Qi(x,D): return (np.sign(x)*np.floor(np.abs(x)/D+DZO)).astype(np.int64)
def Rv(q,D): return np.round(q*D).astype(np.int64)
def canon(v,p,lo,hi,D):
    """v = final value (in [lo,hi]); p = predictor offset; returns canonical index"""
    x=v-p; q=Qi(x,D)
    # clamped values sit on a boundary; canonical index = smallest |q| whose R reaches it
    up=(v==hi)&(v>lo); dn=(v==lo)&(v<hi)
    qu=np.ceil(x/D-1e-9).astype(np.int64)   # smallest q with q*D>=x (approx; exact check below)
    qu=np.where(Rv(qu,D)<x,qu+1,qu); qu=np.where(Rv(qu-1,D)>=x,qu-1,qu)
    qd=np.floor(x/D+1e-9).astype(np.int64)
    qd=np.where(Rv(qd,D)>x,qd-1,qd); qd=np.where(Rv(qd+1,D)<=x,qd+1,qd)
    # only use boundary rule when the ordinary index does NOT reproduce v
    ok=np.clip(Rv(q,D)+p,lo,hi)==v
    q=np.where(~ok&up,qu,q); q=np.where(~ok&dn,qd,q)
    return q
def dq(q,p,lo,hi,D): return np.clip(Rv(q,D)+p,lo,hi)
def choose(t,p,lo,hi,D):
    """encoder value choice: dead-zone index, but a clamped (boundary) neighbour nearer the target wins"""
    q0=Qi(t,D); v0=np.clip(Rv(q0,D)+p,lo,hi); tq=t+p
    q1=q0+np.sign(tq-v0); v1=np.clip(Rv(q1,D)+p,lo,hi)
    use=((v1==lo)|(v1==hi))&(np.abs(v1-tq)<np.abs(v0-tq))
    return np.where(use,v1,v0)
# ---- legal synthesis of one pair step given boxes on outputs ----
def hint(A0,A1,B0,B1,m):
    return np.maximum(2*(A0-m)-1,2*(m-B1)), np.minimum(2*(A1-m),2*(m-B0)+1)
def code_pairstep(tgtL,tgtd,L_is_known,axis,kind,box0,box1,D_m,D_d,enc=True,qm=None,qd_=None):
    """Horizontal/vertical pair synthesis along axis with legality boxes on the OUTPUT samples.
    tgtL: target mean coefficients (or known final means if L_is_known); tgtd: target PREDICTED diffs.
    box0/box1: arrays shaped like output (lo/hi per output sample). Returns (out, qm, qd, bits-inputs)."""
    A0=np.moveaxis(box0,axis,0)[0::2]; A1=np.moveaxis(box1,axis,0)[0::2]
    B0=np.moveaxis(box0,axis,0)[1::2]; B1=np.moveaxis(box1,axis,0)[1::2]
    A0,A1,B0,B1=[np.moveaxis(t,0,axis) for t in (A0,A1,B0,B1)]
    mlo=fl(A0+B0,2); mhi=fl(A1+B1,2)
    if L_is_known: m=tgtL; qm=None
    else:
        if enc: qm=canon(choose(tgtL,0,mlo,mhi,D_m),0,mlo,mhi,D_m)
        m=dq(qm,0,mlo,mhi,D_m)
    p=pred(m,axis,kind); dlo,dhi=hint(A0,A1,B0,B1,m)
    if enc:
        v=choose(tgtd-p,p,dlo,dhi,D_d); qd_=canon(v,p,dlo,dhi,D_d)
    d=dq(qd_,p,dlo,dhi,D_d)
    return ipair(m,d,axis),qm,qd_
def srcpairs(x,axis):
    x=np.moveaxis(x,axis,0); e=x[0::2]; o=x[1::2]
    return np.moveaxis(fl(e+o,2),0,axis), np.moveaxis(e-o,0,axis)
def vbox(Lv,lo,hi):
    return np.maximum(2*(Lv-hi),2*(lo-Lv)-1), np.minimum(2*(hi-Lv),2*(Lv-lo)+1)
def dpcm_canon(v,D,lo,hi,enc=True,qs=None):
    rec=np.zeros_like(v) if enc else np.zeros(qs.shape,dtype=np.int64)
    if enc: qs=np.zeros_like(v)
    Hc,Wc=rec.shape
    for x in range(Wc):
        if x==0:
            p=np.full(Hc,(lo+hi+1)//2,dtype=np.int64)
            # column 0: predict from row above (sequential)
            for y in range(Hc):
                pp=np.array(p[0] if y==0 else rec[y-1,0])
                if enc:
                    vv=choose(np.array(v[y,0]-pp),pp,lo,hi,D); qs[y,0]=canon(np.array(vv),pp,lo,hi,D)
                rec[y,0]=dq(qs[y,0],pp,lo,hi,D)
            continue
        p=rec[:,x-1]
        if enc:
            vv=choose(v[:,x]-p,p,lo,hi,D); qs[:,x]=canon(vv,p,lo,hi,D)
        rec[:,x]=dq(qs[:,x],p,lo,hi,D)
    return rec,qs
def codec(x,steps,Lh,Lv,kv,kh,lo,hi,enc=True,idx=None):
    """steps: dict band-> step. Encoder (enc) from image x; decoder from idx. Returns recon, idx."""
    if enc:
        # source pyramid of raw pairs
        src=[]; ll=x
        for k in range(Lh):
            if k<Lv:
                Lv_,Dv=srcpairs(ll,0); LL,LH=srcpairs(Lv_,1); src.append(('2d',Lv_,Dv,LH)); ll=LL
            else:
                LL,H=srcpairs(ll,1); src.append(('1d',H)); ll=LL
        idx={}
        llr,idx['LL']=dpcm_canon(ll,steps['LL'],lo,hi)
    else:
        llr,_=dpcm_canon(None,steps['LL'],lo,hi,enc=False,qs=idx['LL'])
    for k in range(Lh-1,-1,-1):
        if k>=Lv:
            box=(np.full((llr.shape[0],2*llr.shape[1]),lo),np.full((llr.shape[0],2*llr.shape[1]),hi))
            t=src[k][1] if enc else None
            llr,_,q=code_pairstep(llr,t,True,1,KH,box[0],box[1],None,steps[('H',k)],enc,None,None if enc else idx[('H',k)])
            idx[('H',k)]=q
        else:
            shp=(llr.shape[0],2*llr.shape[1])
            tLH=src[k][3] if enc else None
            Lvr,_,q=code_pairstep(llr,tLH,True,1,KH,np.full(shp,lo),np.full(shp,hi),None,steps[('LH',k)],enc,None,None if enc else idx[('LH',k)])
            idx[('LH',k)]=q
            pv=pred(Lvr,0,KV); dlo,dhi=vbox(Lvr,lo,hi)
            if enc:
                Dvp=src[k][2]-pv; HLt,HHt=srcpairs(Dvp,1)
            else: HLt=HHt=None
            Dvpr,qm,qd_=code_pairstep(HLt,HHt,False,1,KH,dlo-pv,dhi-pv,steps[('HL',k)],steps[('HH',k)],enc,
                                      None if enc else idx[('HL',k)],None if enc else idx[('HH',k)])
            idx[('HL',k)]=qm; idx[('HH',k)]=qd_
            llr=ipair(Lvr,Dvpr+pv,0)
    return llr,idx
KV='26'; KH='26'

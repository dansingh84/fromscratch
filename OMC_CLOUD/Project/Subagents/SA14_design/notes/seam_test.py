"""Seam test (luma): vertical 2-level 5/3 structures with 16-row slices, horizontal 5-level 5/3 on
each vertical band.  V-cont: continuous vertical transform (no slices).  V-mirror: slice-local,
symmetric extension both ends (today's shape).  V-causal: slice rows shifted by one, every predict
two-sided using the slice above's FINAL data (closed loop), bottom update one-sided (detail mirror).
Reports PSNR/entropy and the per-row-phase mean |error| (row index mod 16)."""
import sys, numpy as np
sys.path.insert(0,'.')
import nest, common14 as cm
S=16

def h_fwd(X):
    bands,LL=nest.sep_fwd(X,0,5); return bands,LL
def h_inv(b,LL): return nest.sep_inv(b,LL,0,5)

def v53_fwd_col(x, top=None, bottom_mirror=True):
    """x: (n, W) rows; if top is given, x[0] is an ODD sample predicted from top and x[1]."""
    if top is None:
        e=x[0::2]; o=x[1::2]
        er=np.concatenate([e[1:],e[-1:]],0)
        d=o-((e+er)>>1)
        dl=np.concatenate([d[:1],d[:-1]],0)
        L=e+((dl+d+2)>>2)
        return L,d
    o=x[0::2]; e=x[1::2]
    eu=np.concatenate([top[None,:],e[:-1]],0)
    d=o-((eu+e)>>1)
    dn=np.concatenate([d[1:],d[-1:]],0)       # bottom: detail mirror
    L=e+((d+dn+2)>>2)
    return L,d

def v53_inv_col(L,d,top=None):
    if top is None:
        dl=np.concatenate([d[:1],d[:-1]],0)
        e=L-((dl+d+2)>>2)
        er=np.concatenate([e[1:],e[-1:]],0)
        o=d+((e+er)>>1)
        x=np.empty((e.shape[0]*2,)+e.shape[1:],np.int64); x[0::2]=e; x[1::2]=o; return x
    dn=np.concatenate([d[1:],d[-1:]],0)
    e=L-((d+dn+2)>>2)
    eu=np.concatenate([top[None,:],e[:-1]],0)
    o=d+((eu+e)>>1)
    x=np.empty((e.shape[0]*2,)+e.shape[1:],np.int64); x[0::2]=o; x[1::2]=e; return x

def q_band(v,s): return nest.R(nest.Q(v,s),s)

def code_bands(vb, sh):
    """vb: dict name->array (vertical band); horizontal transform, quantise, entropy, inverse."""
    bits=0; out={}
    for k,v in vb.items():
        hb,LL=h_fwd(v)
        qb=[]
        for lev,b in enumerate(hb):
            s=sh[(k,lev)]; q=nest.Q(b['H'],s); bits+=nest.entropy_bits(q); qb.append({'H':nest.R(q,s)})
        s=sh[(k,'LL')]; q=nest.Q(LL,s); bits+=nest.entropy_bits(q)
        out[k]=h_inv(qb,nest.R(q,s))
    return bits,out

def steps(W,D0):
    # basis energies of the continuous structure (V 2 levels x H 5 levels)
    H=64
    sh={}
    def synth(k,lev):
        X=np.zeros((H,W),np.int64)
        L1,d1=v53_fwd_col(X); L2,d2=v53_fwd_col(L1)
        vb={'LL':L2,'H2':d2,'H1':d1}
        hbs={}
        for kk,v in vb.items():
            hb,LL=h_fwd(v); hbs[kk]=[hb,LL]
        hb,LL=hbs[k]
        if lev=='LL': LL[LL.shape[0]//2,LL.shape[1]//2]=1<<12
        else: hb[lev]['H'][hb[lev]['H'].shape[0]//2,hb[lev]['H'].shape[1]//2]=1<<12
        rec={kk:h_inv(*hbs[kk]) for kk in vb}
        L1r=v53_inv_col(rec['LL'],rec['H2']); Xr=v53_inv_col(L1r,rec['H1'])
        return ((Xr.astype(float)/(1<<12))**2).sum()
    for k in ('LL','H2','H1'):
        for lev in list(range(5))+['LL']:
            sh[(k,lev)]=max(0,int(round(np.log2(D0/np.sqrt(synth(k,lev))))))
    return sh

def run_cont(X,sh):
    L1,d1=v53_fwd_col(X); L2,d2=v53_fwd_col(L1)
    bits,r=code_bands({'LL':L2,'H2':d2,'H1':d1},sh)
    return bits, v53_inv_col(v53_inv_col(r['LL'],r['H2']),r['H1'])

def run_mirror(X,sh):
    bits=0; out=np.empty_like(X)
    for k in range(X.shape[0]//S):
        x=X[k*S:(k+1)*S]
        L1,d1=v53_fwd_col(x); L2,d2=v53_fwd_col(L1)
        b,r=code_bands({'LL':L2,'H2':d2,'H1':d1},sh); bits+=b
        out[k*S:(k+1)*S]=v53_inv_col(v53_inv_col(r['LL'],r['H2']),r['H1'])
    return bits,out

def run_causal(X,sh):
    """slice k covers rows 16k+1 .. 16k+16 (first slice: rows 0..16 handled with row 0 as its own top)."""
    Hh,W=X.shape
    out=np.empty_like(X); bits=0
    # row 0: code as the 'top' of slice 0 with a 1-row intra (tiny) -- use exact value for simplicity
    out[0]=X[0]; top1=X[0].copy(); top2=X[0].copy()   # final pixel row / final level-1 L row above
    r=1
    while r+S<=Hh:
        x=X[r:r+S]
        L1,d1=v53_fwd_col(x,top=top1)            # L1: 8 rows (local rows 1,3,..15 -> abs r+1..r+15)
        L2,d2=v53_fwd_col(L1,top=top2)           # L2: 4 rows
        b,rr=code_bands({'LL':L2,'H2':d2,'H1':d1},sh); bits+=b
        L1r=v53_inv_col(rr['LL'],rr['H2'],top=top2)
        xr=v53_inv_col(L1r,rr['H1'],top=top1)
        out[r:r+S]=xr
        top1=xr[-1].copy(); top2=L1r[-1].copy()
        r+=S
    if r<Hh: out[r:]=X[r:]
    return bits,out

def phase(err,off=0):
    rows=np.abs(err).mean(axis=1)
    ph=np.zeros(S); n=np.zeros(S)
    for i,v in enumerate(rows):
        ph[(i-off)%S]+=v; n[(i-off)%S]+=1
    return ph/n

if __name__=='__main__':
    for cell in ('dng1080','spot'):
        planes,dep=cm.read_frame(cell,8); X=planes[0][:1072]   # multiple of 16 (+ rows for causal)
        M=(1<<dep)-1
        for D0 in (48,128):
            sh=steps(X.shape[1],D0)
            for name,fn,off in (('cont',run_cont,0),('mirror',run_mirror,0),('causal',run_causal,1)):
                b,rec=fn(X,sh); rec=np.clip(rec,0,M); err=rec-X
                ph=phase(err[16:-16],off)
                print(f"{cell} D0={D0} {name:6s} bpp={b/X.size:.4f} psnr={cm.psnr(X,rec,dep):.3f} rowphase(mean|e|, slice row 0..15)=" + ' '.join(f"{v:.2f}" for v in ph)+f"  max/min={ph.max()/ph.min():.3f}",flush=True)

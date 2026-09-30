"""One vertical level (hold at level 1 = continuous vertical transform) vs 2V continuous and 2V causal."""
import sys; sys.argv += ['0']
import numpy as np
sys.path.insert(0,'.')
import seam_test3 as st, hold_test as ht, common14 as cm, nests as nest
S=16
def steps1(W,D0):
    H=64; sh={}
    def en(k,lev):
        X=np.zeros((H,W),np.int64); L1,d1=st.v53_fwd_col(X); vb={'LL':L1,'H1':d1}; hb={kk:list(st.h_fwd(v)) for kk,v in vb.items()}
        b,LL=hb[k]
        if lev=='LL': LL[LL.shape[0]//2,LL.shape[1]//2]=1<<12
        else: b[lev]['H'][b[lev]['H'].shape[0]//2,b[lev]['H'].shape[1]//2]=1<<12
        rec={kk:st.h_inv(*hb[kk]) for kk in vb}; Xr=st.v53_inv_col(rec['LL'],rec['H1'])
        return ((Xr.astype(float)/(1<<12))**2).sum()
    for k in ('LL','H1'):
        for lev in list(range(5))+['LL']: sh[(k,lev)]=max(0,int(round(np.log2(D0/np.sqrt(en(k,lev))))))
    return sh
def run1(X,sh,hold=True):
    Hh,W=X.shape; out=np.empty_like(X); bits=0; out[0]=X[0]; top1=X[0].copy(); r=1; carry=None
    while r+S<=Hh:
        x=X[r:r+S]; nxt=hold and r+S<Hh-1
        dsrc=X[r+S]-((X[r+S-1]+X[r+S+1])>>1) if nxt else np.zeros(W,np.int64)
        dnrec=ht.qrow(dsrc,sh) if nxt else dsrc
        o=x[0::2]; e=x[1::2]; eu=np.concatenate([X[r-1][None,:],e[:-1]],0); d1=o-((eu+e)>>1)
        if carry is not None: d1[0]=carry
        dn=np.concatenate([d1[1:],dnrec[None,:]],0); L1=e+((d1+dn+2)>>2)
        b,rr=st.code_bands({'LL':L1,'H1':d1},sh); bits+=b
        xr=ht.inv1(rr['LL'],rr['H1'],top1,dnrec); out[r:r+S]=xr; top1=xr[-1].copy(); carry=dsrc if nxt else None; r+=S
    if r<Hh: out[r:]=X[r:]
    return bits,out
for cell in ('dng1080','spot'):
    planes,dep=cm.read_frame(cell,8)
    for pi,pn in enumerate(('Y','Cb','Cr')):
        X=planes[pi][:1073]
        for D0 in (48,128):
            s1=steps1(X.shape[1],D0); b,rec=run1(X,s1); rec=np.clip(rec,0,1023); ph=st.phase((rec-X)[16:-16],1)
            s2=st.steps(X.shape[1],D0); bc,rc=st.run_cont(X[:1072],s2); rc=np.clip(rc,0,1023)
            print(f"{cell} {pn} D0={D0}: 1V+hold bpp {b/X.size:.4f} psnr {cm.psnr(X,rec,dep):.2f} rowphase max/min {ph.max()/ph.min():.3f} rows0,1,15 {ph[0]:.2f} {ph[1]:.2f} {ph[15]:.2f} | 2V continuous bpp {bc/X[:1072].size:.4f} psnr {cm.psnr(X[:1072],rc,dep):.2f}",flush=True)

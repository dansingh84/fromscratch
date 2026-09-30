"""One-line hold: the last low row of each causal slice gets its update from the NEXT slice's first detail row
(level 1 only; level 2 stays causal with zero below).  Row-phase error per plane, bits, A5 (next slice lost)."""
import sys; sys.argv += ['0']
import numpy as np
sys.path.insert(0,'.')
import seam_test3 as st, common14 as cm, nests as nest
S=st.S
def fwd1(x, top, dn_last):
    o=x[0::2]; e=x[1::2]
    eu=np.concatenate([top[None,:],e[:-1]],0)
    d=o-((eu+e)>>1)
    dn=np.concatenate([d[1:],dn_last[None,:]],0)
    return e+((d+dn+2)>>2), d
def inv1(L,d,top,dn_last):
    dn=np.concatenate([d[1:],dn_last[None,:]],0)
    e=L-((d+dn+2)>>2)
    eu=np.concatenate([top[None,:],e[:-1]],0)
    o=d+((eu+e)>>1)
    x=np.empty((e.shape[0]*2,)+e.shape[1:],np.int64); x[0::2]=o; x[1::2]=e; return x
def qrow(v, sh):
    hb,LL=st.h_fwd(v[None,:]); qb=[]
    for lev,b in enumerate(hb): s=sh[('H1',lev)]; qb.append({'H':nest.R(nest.Q(b['H'],s),s)})
    s=sh[('H1','LL')]; return st.h_inv(qb,nest.R(nest.Q(LL,s),s))[0]
def run(X, sh, hold=True, lose=None, openloop=False):
    Hh,W=X.shape; out=np.empty_like(X); bits=0
    out[0]=X[0]; top1=X[0].copy(); top2=X[0].copy(); r=1; k=0; carry=None; carry_src=None
    while r+S<=Hh:
        x=X[r:r+S]
        nxt = r+S < Hh-1 and hold
        if nxt:
            dsrc = X[r+S] - ((X[r+S-1] + X[r+S+1])>>1)     # next slice's first detail row, open loop
            dnrec = qrow(dsrc, sh)
        else:
            dsrc = np.zeros(W,np.int64); dnrec = dsrc
        # analysis: level 1 with top final, first detail row overridden by the carried one
        o=x[0::2]; e=x[1::2]
        tsrc = X[r-1] if openloop else top1
        eu=np.concatenate([tsrc[None,:],e[:-1]],0); d1=o-((eu+e)>>1)
        if carry_src is not None: d1[0]=carry_src
        dn=np.concatenate([d1[1:],dnrec[None,:]],0); L1=e+((d1+dn+2)>>2)
        L2,d2=st.v53_fwd_col(L1,top=top2)
        b,rr=st.code_bands({'LL':L2,'H2':d2,'H1':d1},sh); bits+=b
        L1r=st.v53_inv_col(rr['LL'],rr['H2'],top=top2)
        dn_dec = dnrec if (lose is None or k+1 != lose) else np.zeros(W,np.int64)
        if lose is not None and k == lose:
            xr = np.repeat(out[r-1:r],S,0)   # lost slice: concealed by repeating the row above
        else:
            xr=inv1(L1r,rr['H1'],top1,dn_dec)
        out[r:r+S]=xr
        top1=xr[-1].copy(); top2=L1r[-1].copy()
        carry_src = dsrc if nxt else None
        r+=S; k+=1
    if r<Hh: out[r:]=X[r:]
    return bits,out
if __name__=='__main__':
    for cell in ('dng1080','spot'):
        planes,dep=cm.read_frame(cell,8)
        for pi,pn in enumerate('Y Cb Cr'.split()):
            X=planes[pi][:1073]
            for D0 in (48,128):
                sh=st.steps(X.shape[1],D0)
                res=[]
                for h,ol in ((True,True),(False,True)):
                    b,rec=run(X,sh,hold=h,openloop=ol); rec=np.clip(rec,0,1023); ph=st.phase((rec-X)[16:-16],1)
                    res.append((b/X.size,cm.psnr(X,rec,dep),ph))
                bc,recc=st.run_cont(X[:1072],sh); recc=np.clip(recc,0,1023); phc=st.phase((recc-X[:1072])[16:-16],0); phc=np.roll(phc,-1)
                print(f"{cell} {pn} D0={D0} | cont bpp {bc/X.size:.4f} psnr {cm.psnr(X[:1072],recc,dep):.2f} rows0-1,15 {phc[0]:.2f} {phc[1]:.2f} {phc[15]:.2f} max/min {phc.max()/phc.min():.3f}"
                      f" | HOLD+openloop-top bpp {res[0][0]:.4f} psnr {res[0][1]:.2f} rows {res[0][2][0]:.2f} {res[0][2][1]:.2f} {res[0][2][15]:.2f} mm {res[0][2].max()/res[0][2].min():.3f}"
                      f" | openloop-top only bpp {res[1][0]:.4f} psnr {res[1][1]:.2f} rows {res[1][2][0]:.2f} {res[1][2][1]:.2f} {res[1][2][15]:.2f} mm {res[1][2].max()/res[1][2].min():.3f}",flush=True)

# T6 still input, T7 mid-stream join, T8 packet loss + on-demand refresh; lattice-locked (idx) model, dng720.
import os, sys, numpy as np
os.environ.setdefault('TMODE','idx')
from common import *
import seq, cpp
from seq import motion, obmc, steps, Lh, Lv, LO, HI, SH
TH=0.25
def enc_frame(fr,ref1,ref2,D,imask,W,H,V=None):
    if ref1 is None: mcs=None; V=None
    else:
        if V is None: V=motion(ref1[0],ref2[0]) if ref2 is not None else np.zeros((H//16,W//16,2),int)
        mcs=[obmc(ref1[0],V,16,1),obmc(ref1[1],V,16,2),obmc(ref1[2],V,16,2)]
    outs=[];idxs=[];b=0
    for pi,p in enumerate(fr):
        y,ix=cpp.code_plane(p,steps(D,p.shape),Lh,Lv,LO,HI,mc=None if mcs is None else mcs[pi],imask=imask,tmode='idx',theta=TH)
        outs.append(y); idxs.append(ix); b+=sum(cond_entropy_bits(v) for v in ix.values())
    return outs,idxs,V,b
def dec_frame(idxs,ref1,V,D,imask,shapes):
    mcs=None if ref1 is None else [obmc(ref1[0],V,16,1),obmc(ref1[1],V,16,2),obmc(ref1[2],V,16,2)]
    return [cpp.code_plane(None,steps(D,shp),Lh,Lv,LO,HI,mc=None if mcs is None else mcs[pi],imask=imask,enc=False,idx=idxs[pi],tmode='idx',theta=TH)[0] for pi,shp in enumerate(shapes)]
none_intra=lambda k,s: np.zeros(s,bool)
def slice_mask(slices,H):
    fs=[seq.refresh_mask_fn(s,H) for s in slices]
    def f(k,shp):
        m=np.zeros(shp,bool)
        for g in fs: m|=g(k,shp)
        return m
    return f
path,W,H=CELLS['dng720']; which=sys.argv[1]
if which=='still':
    src=read_frame(path,W,H,8); D0=64.0; rec=[]; prev=None; prev2=None
    plan=[D0]*4+[D0/2]*4+[D0]*2
    for t,D in enumerate(plan):
        out,ix,V,b=enc_frame(src,prev,prev2,D,none_intra,W,H)
        if prev is not None:
            ch=[int((a!=c).sum()) for a,c in zip(out,prev)]
            tow=[int(((np.abs(a-s)<np.abs(c-s))&(a!=c)).sum()) for a,c,s in zip(out,prev,src)]
            awy=[int(((np.abs(a-s)>np.abs(c-s))&(a!=c)).sum()) for a,c,s in zip(out,prev,src)]
        else: ch=tow=awy=['-']*3
        print(f'still t={t} D={D:g} bpp={b/(W*H):.4f} psnr={psnr(src[0],out[0]):.2f}/{psnr(src[1],out[1]):.2f}/{psnr(src[2],out[2]):.2f} changed Y/Cb/Cr={ch} toward_src={tow} away={awy}',flush=True)
        prev2=prev; prev=out
elif which in ('join','loss'):
    meta=np.load('../out/dng720_b0.5_idx0.25.meta.npy'); Ds=meta[0]; N=9
    frames=[read_frame(path,W,H,t) for t in range(N)]
    # gen-1 encoder with stored streams (refresh off: on-demand design)
    g1=[];I1=[];V1=[];B1=[]
    for t in range(N):
        o,ix,V,b=enc_frame(frames[t],g1[t-1] if t else None,g1[t-2] if t>1 else None,Ds[t],none_intra,W,H)
        g1.append(o);I1.append(ix);V1.append(V);B1.append(b)
    if which=='join':
        J=4; g2=[]
        for t in range(J,N):
            k=t-J
            o,ix,V,b=enc_frame(g1[t],g2[k-1] if k else None,g2[k-2] if k>1 else None,Ds[t],none_intra,W,H)
            g2.append(o)
            nd=sum(int((a!=c).sum()) for a,c in zip(o,g1[t]))
            print(f'join t={t} (joiner frame {k}) differing samples vs upstream={nd}  bits joiner/upstream={b/B1[t]:.3f}  vectors equal={V is None and V1[t] is None or (V is not None and V1[t] is not None and (V==V1[t]).all())}',flush=True)
    else:
        shapes=[p.shape for p in frames[0]]; L=4; lost=20; RT=2
        dec=[]
        for t in range(N):
            ref=dec[t-1] if t else None
            if t==L:
                # packet of slice `lost` missing: its indices are unknown -> residual 0 (hint only)
                ix=[{k:v.copy() for k,v in d.items()} for d in I1[t]]
                for pi in range(3):
                    for k,v in ix[pi].items():
                        rows,sp=cpp.band_rows(k,v.shape,Lv,H)
                        m=(rows>=SH*lost)&(rows<SH*(lost+1))
                        v[m]=0
                o=dec_frame(ix,ref,V1[t],Ds[t],none_intra,shapes)
            elif t==L+RT:
                # on-demand refresh of the damaged slices (+-1 margin): encoder re-codes those slices hint-free
                M=int(os.environ.get("RM","1")); im=slice_mask(list(range(lost-M,lost+M+1)),H)
                o_enc,ix,V,b=enc_frame(frames[t],g1[t-1],g1[t-2],Ds[t],im,W,H,V=V1[t])
                assert all((a==c).all() for a,c in zip(o_enc,g1[t])), 'refresh changed the encoder picture'
                o=dec_frame(ix,ref,V1[t],Ds[t],im,shapes); print(f'  refresh frame bits / normal = {b/B1[t]:.3f}')
            else:
                o=dec_frame(I1[t],ref,V1[t],Ds[t],none_intra,shapes)
            dec.append(o)
            dif=[(a!=c) for a,c in zip(o,g1[t])]
            rows=np.where(dif[0].any(1))[0]
            print(f'loss t={t} decoder!=encoder samples Y/Cb/Cr={[int(d.sum()) for d in dif]} damaged Y rows={(rows.min(),rows.max()) if len(rows) else None} psnr dec={psnr(frames[t][0],o[0]):.2f} enc={psnr(frames[t][0],g1[t][0]):.2f}',flush=True)

# CPP sequence model: intra frame 0, inter after; motion from decoded history (transmitted), OBMC,
# packet-aligned top-down rolling refresh with ahead-means, clean-region vector clamp; per-frame step
# chosen to meet a target entropy (model stand-in for rate control); gen-2 re-encode check.
import sys, os, numpy as np, time
from common import *
import cpp, t2, tsx
Lh,Lv=5,int(os.environ.get('LV','2')); SH=16; LO,HI=0,1023
cpp.KV=os.environ.get('KV','26')
TMODE=os.environ.get('TMODE','val'); THETA=float(os.environ.get('THETA','0.25'))
def gains_for(shape,cache={}):
    tsx.KV=cpp.KV; tsx.KH='26'
    if shape not in cache: cache[shape]=t2.ts_gains(shape,Lh,Lv)
    return cache[shape]
def steps(D,shape):
    g=gains_for(shape); return {k:max(2.0,D/np.sqrt(v)) for k,v in g.items()}
def down2(a): return (a[0::2,0::2]+a[1::2,0::2]+a[0::2,1::2]+a[1::2,1::2])/4.0
def shifted(a,dy,dx):
    H,W=a.shape; yi=np.clip(np.arange(H)+dy,0,H-1); xi=np.clip(np.arange(W)+dx,0,W-1); return a[yi][:,xi]
def motion(cur,ref,B=16,R=8):
    """backward block vectors u: cur(x) ~ ref(x+u); 2-level search (+-2R full-pel)."""
    H,W=cur.shape; nby,nbx=H//B,W//B
    c2=down2(cur.astype(float)); r2=down2(ref.astype(float)); b2=B//2
    best=np.full((nby,nbx),np.inf); V=np.zeros((nby,nbx,2),int)
    def bsad(a,b,bs):
        d=np.abs(a-b)[:nby*bs,:nbx*bs]; return d.reshape(nby,bs,nbx,bs).sum(axis=(1,3))
    for dy in range(-R,R+1):
        for dx in range(-R,R+1):
            s=bsad(c2,shifted(r2,dy,dx),b2)+0.01*(abs(dy)+abs(dx))
            m=s<best; best[m]=s[m]; V[m]=(2*dy,2*dx)
    cf=cur.astype(float); rf=ref.astype(float); best=np.full((nby,nbx),np.inf); V2=V.copy()
    for ddy in (-1,0,1):
        for ddx in (-1,0,1):
            s=np.zeros((nby,nbx))
            # per-block candidate = V + (ddy,ddx); evaluate via unique vectors
            cand=V+np.array([ddy,ddx])
            for (vy,vx) in set(map(tuple,cand.reshape(-1,2))):
                m=(cand[...,0]==vy)&(cand[...,1]==vx)
                sa=bsad(cf,shifted(rf,vy,vx),B)
                s[m]=sa[m]
            s=s+0.01*(np.abs(cand).sum(-1))
            m=s<best; best[m]=s[m]; V2[m]=cand[m]
    return V2
def obmc(ref,V,B,sx=1):
    """bilinear OBMC over block centres; V in luma units; sx=2 for 4:2:2 chroma (half width)."""
    H,W=ref.shape; Bx=B//sx; nby,nbx=V.shape[:2]
    yc=(np.arange(H)-(B/2-0.5))/B; xc=(np.arange(W)-(Bx/2-0.5))/Bx
    y0=np.clip(np.floor(yc).astype(int),0,nby-1); x0=np.clip(np.floor(xc).astype(int),0,nbx-1)
    y1=np.clip(y0+1,0,nby-1); x1=np.clip(x0+1,0,nbx-1)
    fy=np.clip(np.round((yc-np.floor(yc))*16).astype(int),0,16); fx=np.clip(np.round((xc-np.floor(xc))*16).astype(int),0,16)
    fy=np.where(yc<0,0,np.where(np.floor(yc)>=nby-1,0,fy)); fx=np.where(xc<0,0,np.where(np.floor(xc)>=nbx-1,0,fx))
    acc=np.zeros((H,W),dtype=np.int64)
    Y,X=np.meshgrid(np.arange(H),np.arange(W),indexing='ij')
    for (ya,wy) in ((y0,16-fy),(y1,fy)):
        for (xa,wx) in ((x0,16-fx),(x1,fx)):
            vy=V[ya][:,xa][...,0]; vx=V[ya][:,xa][...,1]
            vx=np.floor_divide(vx,sx) if sx>1 else vx
            g=ref[np.clip(Y+vy,0,H-1),np.clip(X+vx,0,W-1)]
            acc+=np.outer(wy,wx)*g
    return (acc+128)>>8
def refresh_mask_fn(s,H):
    """intra mask: all coefficients of slice s rows; + ahead data for the next two 4-row blocks."""
    r0,r1=SH*s,SH*(s+1)
    def f(key,shape):
        rows,sp=cpp.band_rows(key,shape,Lv,H)
        inside=(rows>=r0)&(rows<r1)
        k=key[1] if isinstance(key,tuple) else None
        b=rows//4  # block index of coefficient row
        nb0=r1//4
        if key=='LL' or key[0]=='H' or (key[0]=='LH' and k==1):
            ahead=(b>=nb0)&(b<nb0+2)
        elif key[0] in ('HL','HH') and k==1: ahead=(b==nb0)
        elif key[0]=='LH' and k==0: ahead=(b==nb0)
        else: ahead=np.zeros_like(inside)
        if cpp.KV=='26c': ahead=np.zeros_like(inside)
        m=(inside|ahead)[:,None]
        return np.broadcast_to(m,shape).copy()
    return f
def encode_seq(frames,target_bits,log,gen1_steps=None,W=None,H=None):
    """frames: list of [Y,Cb,Cr]; returns decodes, per-frame D, bits, refresh slice list"""
    nsl=H//SH; dec=[]; Ds=[]; bits=[]; rs=[]
    for t,fr in enumerate(frames):
        if t==0:
            mcs=None; mf=None; s=None
        else:
            if t>=2: V=motion(dec[t-1][0],dec[t-2][0])
            else: V=np.zeros((H//16,W//16,2),int)
            s=(t-1)%nsl; rs.append(s)
            front=SH*(s+1); pfront=SH*(s)   # rows above pfront were clean after frame t-1
            if t>=2 and (t-1)>0:
                # clean-region clamp: blocks entirely above the new front may not read at/below pfront
                yb=np.arange(V.shape[0])*16+15+8
                lim=(pfront-1-2)-yb
                above=(np.arange(V.shape[0])*16+16)<=front
                if pfront>0:
                    V[...,0]=np.where(above[:,None],np.minimum(V[...,0],lim[:,None]),V[...,0])
            mcs=[obmc(dec[t-1][0],V,16,1),obmc(dec[t-1][1],V,16,2),obmc(dec[t-1][2],V,16,2)]
            mf=refresh_mask_fn(s,H)
        def run(D):
            outs=[];b=0;idxs=[]
            for pi,p in enumerate(fr):
                y,idx=cpp.code_plane(p,steps(D,p.shape),Lh,Lv,LO,HI,mc=None if mcs is None else mcs[pi],imask=mf,tmode=TMODE,theta=THETA)
                outs.append(y); idxs.append(idx); b+=sum(cond_entropy_bits(v) for v in idx.values())
            return outs,b,idxs
        if gen1_steps is not None:
            D=gen1_steps[t]; outs,b,idxs=run(D)
        else:
            lo_,hi_=np.log(2.0),np.log(600.0); best=None
            D=np.exp((lo_+hi_)/2)
            for it in range(7):
                outs,b,idxs=run(D)
                if b<=target_bits: hi_=np.log(D); best=(D,outs,b,idxs)
                else: lo_=np.log(D)
                if best is not None and abs(b-target_bits)<0.02*target_bits and b<=target_bits: break
                D=np.exp((lo_+hi_)/2)
            if best is None: best=(D,outs,b,idxs)
            D,outs,b,idxs=best
        dec.append([o.astype(np.int64) for o in outs]); Ds.append(D); bits.append(b)
        print(f'{log} t={t} D={D:.2f} bpp={b/(W*H):.3f} psnr={psnr(fr[0],outs[0]):.2f}/{psnr(fr[1],outs[1]):.2f}/{psnr(fr[2],outs[2]):.2f} refresh={s}',flush=True)
    return dec,Ds,bits,rs
def write_yuv(path,dec):
    with open(path,'wb') as f:
        for fr in dec:
            for p in fr: f.write(p.astype('<u2').tobytes())
if __name__=='__main__':
    cell=sys.argv[1]; bpp=float(sys.argv[2]); N=int(sys.argv[3]); ovh=float(sys.argv[4]) if len(sys.argv)>4 else 1.10
    path,W,H=CELLS[cell]
    frames=[read_frame(path,W,H,t) for t in range(N)]
    target=bpp*W*H/ovh
    t0=time.time()
    dec,Ds,bits,rs=encode_seq(frames,target,f'{cell}@{bpp} g1',W=W,H=H)
    out='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA15_design/out/'
    tag=f'{cell}_b{bpp}'+('' if TMODE=='val' else f'_idx{THETA}')+('' if (cpp.KV=='26' and Lv==2) else f'_v{cpp.KV}L{Lv}')+('_alt' if getattr(cpp,'ALT',False) else '')+(('_dz'+os.environ['DZ']) if 'DZ' in os.environ else '')
    write_yuv(out+tag+'.cpp.yuv',dec)
    np.save(out+tag+'.meta.npy',np.array([Ds,bits],dtype=float))
    # gen-2
    dec2,_,bits2,_=encode_seq(dec,target,f'{cell}@{bpp} g2',gen1_steps=Ds,W=W,H=H)
    nd=sum(int((a!=b).sum()) for f1,f2 in zip(dec,dec2) for a,b in zip(f1,f2))
    oob=sum(int(((p<LO)|(p>HI)).sum()) for f in dec for p in f)
    print(f'{tag} GEN2 differing samples={nd}  bits g2/g1={sum(bits2)/sum(bits):.4f}  oob={oob}  time={time.time()-t0:.0f}s',flush=True)

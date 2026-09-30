# T1: closed-loop predict-only interpolation (PO-CL) vs open-loop 5/3, intra, same 5H/2V structure.
import numpy as np, sys
from common import *
def fl(a,b): return np.floor_divide(a,b)
def lift53(x,axis,inv=False):
    x=np.moveaxis(x,axis,0).copy()
    if not inv:
        e=x[0::2].copy(); o=x[1::2].copy()
        er=np.concatenate([e[1:],e[-1:]],0)
        d=o-fl(e+er,2)
        dl=np.concatenate([d[:1],d[:-1]],0)
        s=e+fl(dl+d+2,4)
        return np.moveaxis(s,0,axis),np.moveaxis(d,0,axis)
def unlift53(s,d,axis):
    s=np.moveaxis(s,axis,0); d=np.moveaxis(d,axis,0)
    dl=np.concatenate([d[:1],d[:-1]],0)
    e=s-fl(dl+d+2,4)
    er=np.concatenate([e[1:],e[-1:]],0)
    o=d+fl(e+er,2)
    x=np.empty((2*e.shape[0],)+e.shape[1:],dtype=np.int64); x[0::2]=e; x[1::2]=o
    return np.moveaxis(x,0,axis)
def fwd(x,Lh,Lv):
    bands=[]; ll=x
    for k in range(Lh):
        if k<Lv:
            l,h=lift53(ll,0); ll_,lh=lift53(l,1); hl,hh=lift53(h,1)
            bands.append(('2d',lh,hl,hh)); ll=ll_
        else:
            l,h=lift53(ll,1); bands.append(('1d',h)); ll=l
    return ll,bands
def inv(ll,bands):
    for b in reversed(bands):
        if b[0]=='2d':
            _,lh,hl,hh=b; l=unlift53(ll,lh,1); h=unlift53(hl,hh,1); ll=unlift53(l,h,0)
        else: ll=unlift53(ll,b[1],1)
    return ll
def Q(c,D):
    return np.sign(c)*np.floor(np.abs(c)/D+1/3).astype(np.int64)
def R(q,D): return np.round(q*D).astype(np.int64)
def gains(shape,Lh,Lv):
    # synthesis energy gains per band via impulse
    z=np.zeros(shape,dtype=np.int64); ll,b=fwd(z,Lh,Lv); G=[]
    def imp(setter):
        ll2,b2=fwd(z,Lh,Lv); setter(ll2,b2); return (inv(ll2,b2).astype(float)**2).sum()
    # use large amplitude impulse, scaled
    A=1<<12
    for i,bb in enumerate(b):
        g=[]
        for j in range(1,len(bb)):
            def st(ll2,b2,i=i,j=j):
                arr=b2[i][j]; arr[arr.shape[0]//2,arr.shape[1]//2]=A
            g.append(imp(st)/A/A)
        G.append(g)
    def stl(ll2,b2): ll2[ll2.shape[0]//2,ll2.shape[1]//2]=A
    return imp(stl)/A/A,G
def dpcm_left(v,D,lo=0,hi=1023,closed=True):
    # closed-loop DPCM along columns of a small 2-D array, predictor=left (first col: up)
    rec=np.zeros_like(v); qs=np.zeros_like(v)
    for x in range(v.shape[1]):
        if x==0:
            p=np.concatenate([[512],rec[:-1,0]]) if False else None
            p=np.full(v.shape[0],512,dtype=np.int64)
            # vertical DPCM for first column
            col=np.zeros(v.shape[0],dtype=np.int64)
            prev=512
            for y in range(v.shape[0]):
                qq=Q(np.array(v[y,0]-prev),D); r=prev+R(qq,D)
                if closed: r=min(max(r,lo),hi)
                qs[y,0]=qq; rec[y,0]=r; prev=r
            continue
        p=rec[:,x-1]; qq=Q(v[:,x]-p,D); r=p+R(qq,D)
        if closed: r=np.clip(r,lo,hi)
        qs[:,x]=qq; rec[:,x]=r
    return rec,qs
def code53(x,D,Lh,Lv,G):
    ll,b=fwd(x,Lh,Lv); bits=0; nb=[]
    g0,gb=G
    DLL=D/np.sqrt(g0)
    # LL: closed loop DPCM in coefficient domain (no clamp)
    llr,qs=dpcm_left(ll,DLL,closed=False); bits+=cond_entropy_bits(qs)
    for i,bb in enumerate(b):
        arrs=[]
        for j in range(1,len(bb)):
            Db=D/np.sqrt(gb[i][j-1]); q=Q(bb[j],Db); bits+=cond_entropy_bits(q); arrs.append(R(q,Db))
        nb.append((bb[0],)+tuple(arrs))
    y=np.clip(inv(llr,nb),0,1023)
    return y,bits
def interp(a,b,c=None,d=None,taps=2):
    if taps==2: return fl(a+b+1,2)
    return fl(9*(a+b)-(c+d)+8,16)
def codepo(x,D,Lh,Lv,f=1.0,taps=4,lo=0,hi=1023):
    H,W=x.shape; rec=np.zeros_like(x); bits=0
    sv=1<<Lv; sh=1<<Lh
    c,qs=dpcm_left(x[::sv,::sh],D*f**Lh,lo,hi); rec[::sv,::sh]=c; bits+=cond_entropy_bits(qs)
    def hstep(rows,s,Dk):
        nonlocal bits
        E=rec[rows, ::2*s]  # known
        n=E.shape[1]
        a=E; b=np.concatenate([E[:,1:],E[:,-1:]],1)
        if taps==4:
            cL=np.concatenate([E[:,:1],E[:,:-1]],1); dR=np.concatenate([E[:,2:],E[:,-1:],E[:,-1:]],1)[:,:n]
            p=interp(a,b,cL,dR,4)
        else: p=interp(a,b)
        t=x[rows, s::2*s]; q=Q(t-p,Dk); r=np.clip(p+R(q,Dk),lo,hi); rec[rows, s::2*s]=r; bits+=cond_entropy_bits(q)
    def vstep(s,Dk,colstep):
        nonlocal bits
        E=rec[::2*s, ::colstep]; n=E.shape[0]
        a=E; b=np.concatenate([E[1:],E[-1:]],0)
        if taps==4:
            cU=np.concatenate([E[:1],E[:-1]],0); dD=np.concatenate([E[2:],E[-1:],E[-1:]],0)[:n]
            p=interp(a,b,cU,dD,4)
        else: p=interp(a,b)
        t=x[s::2*s, ::colstep]; q=Q(t-p,Dk); r=np.clip(p+R(q,Dk),lo,hi); rec[s::2*s, ::colstep]=r; bits+=cond_entropy_bits(q)
    for k in range(Lh,0,-1):
        s=1<<(k-1)
        if k>Lv:
            hstep(slice(0,None,sv),s,D*f**(k-1))
        else:
            hstep(slice(0,None,2*s),s,D*f**(k-1))
            vstep(s,D*f**(k-1),s)
    return rec,bits
if __name__=='__main__':
    cell=sys.argv[1]; fr=int(sys.argv[2]); path,W,H=CELLS[cell]
    P=read_frame(path,W,H,fr); Lh,Lv=5,2
    Gs=[gains(p.shape,Lh,Lv) for p in P]
    for name,fn in [('53',None),('po4',4),('po4f',4),('po2',2)]:
        for D in [4,8,16,32]:
            tot=0; ps=[]
            for pi,p in enumerate(P):
                if fn is None: y,b=code53(p,D,Lh,Lv,Gs[pi])
                elif name=='po4f': y,b=codepo(p,D,Lh,Lv,0.8,4)
                else: y,b=codepo(p,D,Lh,Lv,1.0,fn)
                tot+=b; ps.append(psnr(p,y))
            print(f'{cell} f{fr} {name:5s} D={D:3d} bpp={tot/(W*H):.3f} Y/Cb/Cr={ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f}',flush=True)

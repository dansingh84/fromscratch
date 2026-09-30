"""E1: intra efficiency, NEST non-separable (leaf-reading update) vs separable integer 5/3.
Same levels (2 x 2-D + 3 x 1-D horizontal), same step rule (power of two from synthesis
basis energy), same dead-zone quantiser, rate = sum of per-band zeroth-order entropies.
Reports per plane BD-rate (NEST vs 5/3) over D0 in {16..256}."""
import sys, numpy as np
sys.path.insert(0,'.')
import nests as nest, common14 as cm
cm.nest = nest
n2d,n1d=2,3
D0S=(12,16,24,32,48,64,96,128,192,256)

def sep_shifts(shape,D0):
    bands,X=nest.sep_fwd(np.zeros(shape,np.int64),n2d,n1d)
    sh={}
    def en(lev,name):
        b=[{k:np.zeros_like(v) for k,v in bl.items()} for bl in bands]; t=np.zeros_like(X)
        if name=='LL': t[t.shape[0]//2,t.shape[1]//2]=1<<12
        else: b[lev][name][b[lev][name].shape[0]//2,b[lev][name].shape[1]//2]=1<<12
        r=nest.sep_inv(b,t,n2d,n1d).astype(np.float64)/(1<<12); return (r**2).sum()
    for lev,bl in enumerate(bands):
        for k in bl: sh[(lev,k)]=max(0,int(round(np.log2(D0/np.sqrt(en(lev,k))))))
    sh['LL']=max(0,int(round(np.log2(D0/np.sqrt(en(None,'LL'))))))
    return sh

def rd_sep(X,dep):
    pts=[]
    bands,LL=nest.sep_fwd(X,n2d,n1d)
    for D0 in D0S:
        sh=sep_shifts(X.shape,D0); bits=0; qb=[]
        for lev,bl in enumerate(bands):
            d={}
            for k,v in bl.items():
                q=nest.Q(v,sh[(lev,k)]); bits+=nest.entropy_bits(q); d[k]=nest.R(q,sh[(lev,k)])
            qb.append(d)
        q=nest.Q(LL,sh['LL']); bits+=nest.entropy_bits(q)
        rec=np.clip(nest.sep_inv(qb,nest.R(q,sh['LL']),n2d,n1d),0,(1<<dep)-1)
        pts.append((bits/X.size,cm.psnr(X,rec,dep)))
    return pts

def rd_nest(X,dep):
    pts=[]
    lo=np.full(X.shape,-nest.INF); hi=np.full(X.shape,nest.INF)
    levels,(L,_,_)=nest.analysis(X,lo,hi,n2d,n1d)
    for D0 in D0S:
        sh=cm.shifts_for(n2d,n1d,X.shape,D0); bits=0; ql=[]
        for lev,lvl in enumerate(levels):
            d={}
            for n,dd in lvl.items():
                if n=='win': continue
                q=nest.Q(dd['val'],sh[(lev,n)]); bits+=nest.entropy_bits(q)
                d[n]={'val':nest.R(q,sh[(lev,n)]),'esc':np.zeros(q.shape,np.int8)}
            ql.append(d)
        q=nest.Q(L,sh['top']); bits+=nest.entropy_bits(q)
        rec,_,_=nest.synthesis({'val':nest.R(q,sh['top']),'esc':np.zeros(q.shape,np.int8)},ql,lo,hi,n2d,n1d)
        rec=np.clip(rec,0,(1<<dep)-1)
        pts.append((bits/X.size,cm.psnr(X,rec,dep)))
    return pts

def bdrate(a,b):
    """BD-rate of b vs a (percent), piecewise-linear log-rate interpolation over the overlap."""
    a=sorted(a,key=lambda t:t[1]); b=sorted(b,key=lambda t:t[1])
    pa=np.array([t[1] for t in a]); ra=np.log(np.array([t[0] for t in a]))
    pb=np.array([t[1] for t in b]); rb=np.log(np.array([t[0] for t in b]))
    lo_=max(pa.min(),pb.min()); hi_=min(pa.max(),pb.max())
    g=np.linspace(lo_,hi_,200)
    return 100*(np.exp(np.mean(np.interp(g,pb,rb)-np.interp(g,pa,ra)))-1)

if __name__=='__main__':
    wd=int(sys.argv[1]) if len(sys.argv)>1 else 0
    nest.WD=1; nest.TCLIP=wd
    cells=sys.argv[2].split(',') if len(sys.argv)>2 else ['dng1080','spot','floor','gfx']
    for cell in cells:
        planes,dep=cm.read_frame(cell,8)
        row=[]
        for pn,X in zip(('Y','Cb','Cr'),planes):
            a=rd_sep(X,dep); b=rd_nest(X,dep)
            row.append(f"{pn} BD-rate {bdrate(a,b):+.2f}% (psnr@D0=64 sep {a[5][1]:.2f}/{a[5][0]:.3f}bpp nest {b[5][1]:.2f}/{b[5][0]:.3f}bpp)")
        print(f"T={wd} {cell}: "+' | '.join(row),flush=True)

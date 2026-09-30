import sys; sys.path.insert(0,'.')
import numpy as np, nests, common14 as cm, run_e1 as r
cm.nest = nests; nests.WD = 1; nests.TCLIP = 0
def rd(X, dep, mins):
    lo=np.full(X.shape,-nests.INF); hi=np.full(X.shape,nests.INF)
    levels,(L,_,_)=nests.analysis(X,lo,hi,2,3); pts=[]
    for D0 in (6,8,12,16,24,32,48,64,96,128):
        sh={k:max(mins,v) for k,v in cm.shifts_for(2,3,X.shape,D0).items()}; bits=0; ql=[]
        for lev,lvl in enumerate(levels):
            d={}
            for n,dd in lvl.items():
                if n=='win': continue
                q=nests.Q(dd['val'],sh[(lev,n)]); bits+=nests.entropy_bits(q); d[n]={'val':nests.R(q,sh[(lev,n)]),'esc':np.zeros(q.shape,np.int8)}
            ql.append(d)
        q=nests.Q(L,sh['top']); bits+=nests.entropy_bits(q)
        rec,_,_=nests.synthesis({'val':nests.R(q,sh['top']),'esc':np.zeros(q.shape,np.int8)},ql,lo,hi,2,3)
        pts.append((bits/X.size,cm.psnr(X,np.clip(rec,0,(1<<dep)-1),dep)))
    return pts
for cell in ('dng1080','spot','gfx'):
    p,dep=cm.read_frame(cell,8); out=[]
    for pn,X in zip('YBR',p):
        a=rd(X,dep,0); b=rd(X,dep,1)
        out.append(f"{pn} {r.bdrate(a,b):+.2f}% (hi-rate pt: min0 {a[0][0]:.2f}bpp/{a[0][1]:.2f}dB min1 {b[0][0]:.2f}/{b[0][1]:.2f})")
    print(cell,' | '.join(out),flush=True)
X=cm.synth_rails(dep=10); a=rd(X,10,0); b=rd(X,10,1); print('rails', f"{r.bdrate(a,b):+.2f}%", a[:3], b[:3])

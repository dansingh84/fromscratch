"""IDQ capacity per plan: worst virtual error E = sum_b (step_b/2) * L1(synthesis basis_b) (+ rounding),
worst overshoot in steps k = ceil(E/step_b)+1 must fit T_min(b) = floor((M - floor(M/step_b))/2)."""
import sys; sys.path.insert(0,'.')
import numpy as np, nests, common14 as cm, nv4frame as F
cm.nest=nests; nests.WD=1; nests.TCLIP=0
def l1(shape,lev,name):
    lo=np.full(shape,-nests.INF); hi=np.full(shape,nests.INF)
    levels,(L,_,_)=nests.analysis(np.zeros(shape,np.int64),lo,hi,2,3)
    ql=[]
    for lv,lvl in enumerate(levels):
        d={}
        for n,dd in lvl.items():
            if n=='win': continue
            v=np.zeros_like(dd['val'])
            if lv==lev and n==name: v[v.shape[0]//2,v.shape[1]//2]=1<<16
            d[n]={'val':v,'esc':np.zeros(v.shape,np.int8)}
        ql.append(d)
    tv=np.zeros_like(L)
    if name=='top': tv[tv.shape[0]//2,tv.shape[1]//2]=1<<16
    rec,_,_=nests.synthesis({'val':tv,'esc':np.zeros(tv.shape,np.int8)},ql,lo,hi,2,3)
    a=np.abs(rec)/(1<<16)
    my,mx=DEC[(lev,name)] if name!='top' else DEC['top']
    ph=np.zeros((my,mx))
    for y in range(my):
        for x in range(mx): ph[y,x]=a[y::my,x::mx].sum()
    return ph.max()
shape=(64,256)
DEC={(0,'B'):(2,2),(0,'C'):(2,2),(0,'D'):(2,2),(1,'B'):(4,4),(1,'C'):(4,4),(1,'D'):(4,4),(2,'B'):(4,8),(3,'B'):(4,16),(4,'B'):(4,32),'top':(4,32)}
bands=[(l,n) for l in range(2) for n in 'BCD']+[(l,'B') for l in range(2,5)]+['top']
L1={b:(l1(shape,None,'top') if b=='top' else l1(shape,b[0],b[1])) for b in bands}
print('per-pixel worst sum |basis| (L-inf gain):',{str(k):round(v,3) for k,v in L1.items()})
worst_ok=True
for dep,scale in ((8,0.25),(10,1),(12,4)):
    M=(1<<dep)-1
    for D0 in (24,32,48,64,96,128,160,256,384):
        sh=F.plan_rule(shape,int(D0*scale))
        E=sum(((1<<sh[b])/2)*L1[b] for b in bands)+2*len(bands)
        rows=[]; ok=True
        for b in bands:
            D=1<<sh[b]; k=int(np.ceil(E/D))+1; T=(M-M//D)//2
            ok&=k<=T; rows.append(f"{str(b)}:k{k}/T{T}")
        worst_ok&=ok
        print(f"{dep}-bit D0={int(D0*scale)}: E={E:.0f} codes  all bands fit={ok}  "+' '.join(rows))
print('ALL PLANS FIT:',worst_ok)

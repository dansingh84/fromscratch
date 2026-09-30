import sys, numpy as np
sys.path.insert(0,'.')
import nest, common14 as cm
n2d,n1d=2,3
def probe(X,dep,D0,margin):
    M=(1<<dep)-1; lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,M,np.int64)
    sh=cm.shifts_for(n2d,n1d,X.shape,D0)
    levels,(L,tlo,thi)=nest.analysis(X,lo,hi,n2d,n1d)
    ql=[]
    for lev,lvl in enumerate(levels):
        d2={}
        for n,d in lvl.items():
            if n=='win': continue
            s=sh[(lev,n)]; d2[n]={'val':nest.R(nest.Q(d['val'],s),s),'esc':d['esc'].copy()}
        ql.append(d2)
    st=sh['top']; top={'val':nest.R(nest.Q(L,st),st),'esc':np.where(L>=thi,1,np.where(L<=tlo,-1,0)).astype(np.int8)}
    hist=[]
    for it in range(40):
        # margin version of violation: recompute pre-clamp with windows
        rec,vt,vl=nest.synthesis(top,ql,lo,hi,n2d,n1d)
        per=[int((vt!=0).sum())]
        top['esc']=np.where(vt!=0,vt,top['esc']).astype(np.int8)
        for lev in range(n2d+n1d):
            c=0
            for n,v in vl[lev].items():
                c+=int((v!=0).sum()); ql[lev][n]['esc']=np.where(v!=0,v,ql[lev][n]['esc']).astype(np.int8)
            per.append(c)
        hist.append(per)
        if sum(per)==0: break
    return hist, cm.psnr(X,rec,dep)
for cell,f in (('spot',8),('spot',16),('dng1080',8),('floor',8)):
    planes,dep=cm.read_frame(cell,f)
    for D0 in (32,128,256):
        h,p=probe(planes[0],dep,D0,0)
        print(cell,f,D0,'rounds',len(h),'psnr %.2f'%p,'per-round [top,l0..l4]:',h[:9])

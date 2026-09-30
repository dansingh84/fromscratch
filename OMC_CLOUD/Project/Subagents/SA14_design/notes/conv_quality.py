import sys, numpy as np
sys.path.insert(0,'.')
import nest, common14 as cm
n2d,n1d=2,3
for cell,f in (('spot',8),('floor',8),('dng1080',8)):
    planes,dep=cm.read_frame(cell,f); X=planes[0]; M=(1<<dep)-1
    lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,M,np.int64)
    loI=np.full(X.shape,-nest.INF); hiI=np.full(X.shape,nest.INF)
    for D0 in (64,128,256):
        sh=cm.shifts_for(n2d,n1d,X.shape,D0)
        ql,top,rec,st=nest.encode_intra(X,lo,hi,n2d,n1d,sh)
        # reference: same quantised leaves, no escapes (except analysis ones -> keep), unbounded synthesis then clip
        levels,(L,tlo,thi)=nest.analysis(X,lo,hi,n2d,n1d)
        ql0=[]
        for lev,lvl in enumerate(levels):
            d2={}
            for n,d in lvl.items():
                if n=='win': continue
                s=sh[(lev,n)]; d2[n]={'val':nest.R(nest.Q(d['val'],s),s),'esc':d['esc'].copy()}
            ql0.append(d2)
        st_=sh['top']; top0={'val':nest.R(nest.Q(L,st_),st_),'esc':np.zeros(L.shape,np.int8)}
        rec0,_,_=nest.synthesis(top0,ql0,loI,hiI,n2d,n1d)
        clip=np.clip(rec0,0,M)
        diff=np.abs(rec-clip); eC=np.abs(rec-X); eK=np.abs(clip-X); print("  err_vs_src: closure max",int(eC.max()),">64:",int((eC>64).sum()),"| clip max",int(eK.max()),">64:",int((eK>64).sum()));
        print(f"{cell} D0={D0} conv={st['converted']} psnr_closure={cm.psnr(X,rec,dep):.3f} psnr_clip={cm.psnr(X,clip,dep):.3f} oob_unclipped={int(((rec0<0)|(rec0>M)).sum())} px_differ_vs_clip={int((diff>0).sum())} max|diff|={int(diff.max())} px_diff>4={int((diff>4).sum())}",flush=True)

import sys, numpy as np
sys.path.insert(0,'.')
import nest, common14 as cm, oneshot
n2d,n1d=2,3
for cell,f in (('spot',8),('spot',16),('dng1080',8),('floor',8),('gfx',8)):
    planes,dep=cm.read_frame(cell,f)
    X=planes[0]; M=(1<<dep)-1
    lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,M,np.int64)
    for D0 in (32,128,256):
        sh=cm.shifts_for(n2d,n1d,X.shape,D0)
        _,_,recE,stE=nest.encode_intra(X,lo,hi,n2d,n1d,sh)
        for tg in (0,1,2):
            ql,top,rec,st=oneshot.encode_oneshot(X,lo,hi,n2d,n1d,sh,tighten=tg)
            # exactness check through reading
            desc,bits=nest.read_description(ql,top); y1=nest.decode_description(desc,lo,hi,n2d,n1d)
            ql2,top2=nest.canonical_leaves(y1,lo,hi,n2d,n1d); d2,b2=nest.read_description(ql2,top2)
            y2=nest.decode_description(d2,lo,hi,n2d,n1d)
            nearrail=int(((rec!=recE)).sum())
            print(f"{cell} f{f} D0={D0} tighten={tg} exact_closure: conv={stE['converted']} rounds={stE['iters']} psnr={cm.psnr(X,recE,dep):.3f} | oneshot: conv={st['converted']} left={st['violations_left']} psnr={cm.psnr(X,rec,dep):.3f} px_differ={nearrail} oob={int(((y1<0)|(y1>M)).sum())} gen2_moved={int((y2!=y1).sum())}",flush=True)

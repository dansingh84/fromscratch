import sys; sys.path.insert(0,'.')
import numpy as np, importlib, common14 as cm, t_v2_intra as t
REF=int(sys.argv[1]) if len(sys.argv)>1 else 0
def cliprefdec(X, dep, D0, lov=0, hiv=None):
    import nv2; importlib.reload(nv2)
    M=(1<<dep)-1; hiv=M if hiv is None else hiv
    lo=np.full(X.shape,lov,np.int64); hi=np.full(X.shape,hiv,np.int64)
    sh=t.shifts(X.shape,D0); P=t.intra_params(X,sh)
    q,qt=nv2.encode(X,P,lo,hi)
    leaf=[{n:P.cp[l][n]+(q[l][n]<<sh[(l,n)]) for n in q[l]} for l in range(nv2.NL)]
    _,(tlo,thi)=nv2.windows(nv2.upd_values(leaf),lo,hi); P.cp_top=tlo.copy()
    if REF: q,qt,_=nv2.refine(X,q,qt,P,lo,hi)
    y_idq,_=nv2.decode(q,qt,P,lo,hi)
    nv2.idq=lambda pred,q_,s,l,h,qm: pred+(q_<<s)
    big=10**7; yb,_=nv2.decode(q,qt,P,lo-big,hi+big); yc=np.clip(yb,lov,hiv)
    return y_idq, yc, nv2.bits_of(q,qt)/X.size
if __name__=='__main__':
    for D0 in (32,128,256):
        for name,X,dep in (('rails10',cm.synth_rails(dep=10),10),('spot',cm.read_frame('spot',8)[0][0],10)):
            yi,yc,b=cliprefdec(X,dep,D0)
            e=np.abs(yi-X); d=np.abs(yi-yc)
            print(f"{name} D0={D0} bits={b:.4f} psnr IDQ={cm.psnr(X,yi,dep):.3f} clipref(same indices)={cm.psnr(X,yc,dep):.3f}  px differ={int((d>0).sum())} max|IDQ-clip|={int(d.max())}")

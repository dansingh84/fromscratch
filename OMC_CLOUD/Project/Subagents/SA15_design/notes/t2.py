import sys,numpy as np
from common import *
import tsx
from t1_po_vs_53 import gains, code53
def ts_steps(D,Lh,Lv,gs):
    return {k:max(2.0,D/np.sqrt(g)) for k,g in gs.items()}
def ts_gains(shape,Lh,Lv):
    # numerical synthesis gains: unconstrained (huge box) decode of a single index
    lo,hi=-10**9,10**9; x=np.zeros(shape,dtype=np.int64)
    st={'LL':1.0}
    for k in range(Lh):
        for b in (['LH','HL','HH'] if k<Lv else ['H']): st[(b,k)]=1.0
    _,idx0=tsx.codec(x,st,Lh,Lv,tsx.KV,tsx.KH,lo,hi)
    g={}
    for key in st:
        idx={k:np.zeros_like(v) for k,v in idx0.items()}
        a=idx[key]; a[a.shape[0]//2,a.shape[1]//2]=4096
        r,_=tsx.codec(None,st,Lh,Lv,tsx.KV,tsx.KH,lo,hi,enc=False,idx=idx)
        g[key]=(r.astype(float)**2).sum()/4096**2
    return g
if __name__=='__main__':
    cell=sys.argv[1]; fr=int(sys.argv[2]); kind=sys.argv[3]; Lv=int(sys.argv[4]); Ds=[float(a) for a in sys.argv[5].split(',')]
    kv=sys.argv[6] if len(sys.argv)>6 else kind
    tsx.KV=kv; tsx.KH=kind
    path,W,H=CELLS[cell]; P=read_frame(path,W,H,fr); Lh=5
    for D in Ds:
        tot=0; ps=[]; oob=0; g2=0; moved=0
        for p in P:
            gs=ts_gains(p.shape,Lh,Lv); st=ts_steps(D,Lh,Lv,gs)
            y,idx=tsx.codec(p,st,Lh,Lv,kv,kind,0,1023)
            yd,_=tsx.codec(None,st,Lh,Lv,kv,kind,0,1023,enc=False,idx=idx)
            assert (yd==y).all()
            b=sum(cond_entropy_bits(v) for v in idx.values() if v is not None)
            tot+=b; ps.append(psnr(p,y)); oob+=int(((y<0)|(y>1023)).sum())
            y2,idx2=tsx.codec(y,st,Lh,Lv,kv,kind,0,1023)
            g2+=int((y2!=y).sum())+sum(int((idx2[k]!=idx[k]).sum()) for k in idx if idx[k] is not None)
        print(f'{cell} f{fr} TS{kind}/v{kv} Lv={Lv} D={D:g} bpp={tot/(W*H):.3f} Y/Cb/Cr={ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f} oob={oob} gen2diff={g2}',flush=True)

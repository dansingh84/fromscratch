import numpy as np, sys, math
sys.argv=['x']; import hf
rng=np.random.default_rng(7)
def synth(H,W,lo,hi):
    x=np.full((H,W),lo,np.int64)
    # rail plates with dense text-like edges, 1-px lines, checkerboards, near-rail ramps, noise at rails
    x[:, W//4:W//2]=hi
    m=rng.random((H,W))<0.3; x[m]=np.where(rng.random(m.sum())<.5,lo,hi)
    x[::7,:]=hi; x[:, ::5]=lo
    cb=((np.arange(H)[:,None]//1+np.arange(W)[None,:]//1)%2==0); x[H//2:, 3*W//4:]=np.where(cb[H//2:,3*W//4:],lo,hi)
    ramp=np.linspace(lo,lo+8,W)[None,:]; x[:H//4, W//2:3*W//4]=np.rint(ramp[:, W//2:3*W//4]+rng.integers(-3,4,(H//4,W//4)))
    return np.clip(x,lo,hi)
tot=0; bad=0
for depth in (8,10,12):
  for (rn,lo,hi) in (('full',0,2**depth-1),('lim',16<<(depth-8),235<<(depth-8)),('sdi',4<<(depth-10) if depth>=10 else 1, (1019<<(depth-10)) if depth>=10 else 254)):
    for sh,nv,kV,causal in ((8,3,'s10a',True),(16,3,'s10a',True),(16,2,'s6',False)):
      P=synth(64,256,lo,hi)
      for Qf in [x+depth-10 for x in (4,7,10,12)]:
        for kll in (-2,0):
          b,ps,oor,rt0,g2,ph,ncl=hf.code_plane(P,sh,5,nv,'s10',kV,causal,Qf,kll,lo,hi,depth,{})
          tot+=1
          if oor or not rt0 or not g2: bad+=1; print('FAIL',depth,rn,sh,nv,kV,Qf,kll,oor,rt0,g2)
print('cases',tot,'fail',bad)

import sys, numpy as np
sys.path.insert(0,"harness")
import uc_gallery as G
from numpy.lib.stride_tricks import sliding_window_view
w=256
cx=cy=w/2.0; rmax=np.hypot(cx,cy)
f=lambda X,Y: 0.5+0.5*np.cos(2*np.pi*(np.pi*0.45*((X-cx)**2+(Y-cy)**2)/rmax)/np.pi*0.5)
truth=G.render(f,w,w,2,G.LO,G.HI)
src=np.clip(np.round(G.ref_down2(truth)),0,1023).astype(np.int64)
fr=[(src,src[:,::2].copy(),src[:,::2].copy())]
full=G.uc_up(fr,w,w,"422",10)[0][0].astype(np.int64)
sep =G.uc_up(fr,w,w,"422",10,direction=False)[0][0].astype(np.int64)
lin =np.clip(np.round(G.ref_up2(src.astype(float),"lanczos4")),0,1023).astype(np.int64)
print("NATIVE 10-bit, full 2x zone plate %dx%d = %d samples"%(2*w,2*w,4*w*w))
for nm,a,b in (("OMC-UC vs spine",full,sep),("OMC-UC vs lanczos4",full,lin),("spine vs lanczos4",sep,lin)):
    d=np.abs(a-b); print("  %-22s max %4d   >64: %5d   >256: %4d   mean %.2f"%(nm,d.max(),(d>64).sum(),(d>256).sum(),d.mean()))
d=np.abs(full-sep)
win=sliding_window_view(np.pad(sep,4,mode='edge'),(9,9)).mean(axis=(2,3))
inv=((full-win)*(sep-win)<0)&(d>160)
print("\n  polarity-inverted samples (|diff|>160 codes, wrong side of local mean): %d of %d (%.3f%%)"%(inv.sum(),d.size,100*inv.mean()))
ys,xs=np.where(inv)
if len(ys):
    print("  worst deviation %d codes; PSNR-scale: source range %d..%d"%(d[inv].max(),src.min(),src.max()))
    # cluster sizes
    lab=np.zeros_like(inv,int); seen=set(); sizes=[]
    pts=set(zip(ys.tolist(),xs.tolist()))
    while pts:
        st=[pts.pop()]; n=0
        while st:
            y,x=st.pop(); n+=1
            for dy in(-1,0,1):
                for dx in(-1,0,1):
                    p=(y+dy,x+dx)
                    if p in pts: pts.discard(p); st.append(p)
        sizes.append(n)
    print("  %d isolated clusters, sizes: %s"%(len(sizes),sorted(sizes,reverse=True)[:12]))
    print("  corner 128x128 (the published panel) contains %d of them"%int(inv[:128,:128].sum()))

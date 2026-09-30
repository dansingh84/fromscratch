import numpy as np, sys, yuv, ent, seq
cell=sys.argv[1]; bpp=float(sys.argv[2]); N=int(sys.argv[3]); jf=int(sys.argv[4]); lf=int(sys.argv[5]); ls=int(sys.argv[6])
p,W,H=yuv.CELLS[cell]; tabs=ent.Tables(__import__('os').environ.get('TABS','../out/tab_eb_r2.pkl')); kw=dict(tilt=0.25,rho=0.35,bx=64,lam=4,still_hold=1,refresh=int(__import__('os').environ.get('REFRESH','0')))
g1=seq.Seq(W,H,bpp,tabs,**kw); g2=seq.Seq(W,H,bpp,tabs,**kw); g2.universal=True; g3=seq.Seq(W,H,bpp,tabs,**kw); g3.universal=True
gj=seq.Seq(W,H,bpp,tabs,**kw); gj.universal=True; dl=seq.Decoder(g1); dj=None
same=lambda a,b: sum(int((x!=y).sum()) for x,y in zip(a,b))
nf=yuv.nframes(p,W,H)
for f in range(N):
    x=yuv.read_frame(p,W,H,f%nf); o1,b1,i1=g1.encode(x); o2,b2,i2=g2.encode(o1); o3,b3,i3=g3.encode(o2)
    d=dl.decode(i1,lost=(ls,) if f==lf else ())
    s='-'
    if f>=jf:
        oj,bj,ij=gj.encode(o1); s='%d bits %s'%(same(o1,oj),'same' if np.allclose(b1,bj) else 'diff')
    if dj is None and f==jf: dj=seq.Decoder(g1)
    sd=same(o1,dj.decode(i1)) if dj is not None else '-'
    print('f%2d gen2 %d %s gen3 %d | encoder-join %s | decoder-join %s | loss %d | over %d'%(f,same(o1,o2),'same' if np.allclose(b1,b2) else 'DIFF',same(o2,o3),s,sd,same(o1,d),i1['over']),flush=True)

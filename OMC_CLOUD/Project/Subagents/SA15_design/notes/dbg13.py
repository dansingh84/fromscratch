import os; os.environ['TABLES']='../out/tables_B.pkl'; os.environ['DBGR']='1'
import numpy as np, seq2
A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv'; W,H=448,256
c=seq2.Codec(W,H,S=8,tabs=seq2.Tables())
y0=c.encode(seq2.read(A,W,H,0),0.5*W*8)
print('after f0: t',c.t,'len dec',len(c.dec),'credit',round(c.credit),'kprev',c.kprev[:3])
c2=seq2.Codec(W,H,S=8,tabs=seq2.Tables()); c2.ivl=c2.ivl_of(seq2.read(A,W,H,0)); z0=c2._encode(seq2.read(A,W,H,0),0.5*W*8)
print('plain f0 same pic',all((a==b).all() for a,b in zip(y0,z0)),'t',c2.t,'credit',round(c2.credit),'kprev',c2.kprev[:3])
y1=c.encode(seq2.read(A,W,H,1),0.5*W*8)
print('--- plain path on c2')
f1=seq2.read(A,W,H,1); snap=c2.snapshot(); c2.ivl=c2.ivl_of(f1); y=c2._encode(f1,0.5*W*8); k1=list(c2.frame_info['kap'])
c2.restore(snap); c2.ivl=c2.ivl_of(y); c2._encode(y,0.5*W*8); print('plain gen1',k1[:4],'read',c2.frame_info['kap'][:4])

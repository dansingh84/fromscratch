# T5: does the legal box mechanism ever put a sample further from the source than
# "same codec without legality, then per-sample clip"? Intra, all planes.
import sys, numpy as np
from common import *
import tsx, t2
cell=sys.argv[1]; fr=int(sys.argv[2]); Ds=[float(a) for a in sys.argv[3].split(',')]
kv=sys.argv[4] if len(sys.argv)>4 else '26'; Lv=int(sys.argv[5]) if len(sys.argv)>5 else 2
tsx.KV=kv; tsx.KH='26'
path,W,H=CELLS[cell]; P=read_frame(path,W,H,fr); Lh=5
for D in Ds:
    line=[]
    for nm,p in zip(('Y','Cb','Cr'),P):
        st=t2.ts_steps(D,Lh,Lv,t2.ts_gains(p.shape,Lh,Lv))
        yl,il=tsx.codec(p,st,Lh,Lv,kv,'26',0,1023)
        yu,iu=tsx.codec(p,st,Lh,Lv,kv,'26',-10**6,10**6)
        bl=sum(cond_entropy_bits(v) for v in il.values()); bu=sum(cond_entropy_bits(v) for v in iu.values())
        yc=np.clip(yu,0,1023)
        el=np.abs(yl-p); ec=np.abs(yc-p)
        changed=(yl!=yc); worse=el>ec; better=el<ec
        line.append(f'{nm}: oob_unconstr={int(((yu<0)|(yu>1023)).sum())} changed={int(changed.sum())} better={int(better.sum())} worse={int(worse.sum())} maxworse={int((el-ec)[worse].max()) if worse.any() else 0} sumworse={int((el-ec)[worse].sum())} sumbetter={int((ec-el)[better].sum())} psnr legal/clip={psnr(p,yl):.3f}/{psnr(p,yc):.3f} bits legal/clip={bl/bu:.4f}')
    print(f'{cell} f{fr} D={D:g} v{kv}L{Lv} | '+' | '.join(line),flush=True)

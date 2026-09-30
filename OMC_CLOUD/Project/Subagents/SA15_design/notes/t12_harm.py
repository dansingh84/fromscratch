# legality mechanism effect, v2 codec, intra, all planes: same open-loop choices with and without decoder boxes
import numpy as np, cpp2, seq2
from common import cond_entropy_bits
from t2v import gains, field
Lh,Lv=5,2
cells=[('gfx','/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv',448,256,3),
       ('cut24','/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/cut24.yuv',256,64,5),
       ('ext10','/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_10_422_l0.yuv',512,128,1),
       ('dng720','/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv',1280,720,8)]
import sys
sel=sys.argv[1:] or [c[0] for c in cells]
for nm,path,W,H,f in [c for c in cells if c[0] in sel]:
    P=seq2.read(path,W,H,f)
    for kap in (40,48,56,64,72):
        se=[0.0,0.0]; tot={'cl':0,'tow':0,'away':0,'awayclip':0,'maxaway':0,'bits':[0,0],'oobU':0}
        for p in P:
            g=gains(p.shape); T=cpp2.analysis(p,Lh,Lv); Df=field({k:v.shape for k,v in T.items()},kap,g)
            A,oa=cpp2.code_plane(T,None,Df,None,0,1023,Lh,Lv,None,None)
            U,ou=cpp2.code_plane(T,None,Df,None,-10**7,10**7,Lh,Lv,None,None,mid=512)
            C=np.clip(U,0,1023); ch=A!=U; se[0]+=((A-p)**2).sum(); se[1]+=((C-p)**2).sum()
            tot['cl']+=int(ch.sum()); tot['oobU']+=int(((U<0)|(U>1023)).sum())
            ea,eu,ec=np.abs(A-p),np.abs(U-p),np.abs(C-p)
            tot['tow']+=int((ch&(ea<eu)).sum()); tot['away']+=int((ch&(ea>eu)).sum())
            tot['awayclip']+=int((ea>ec).sum()); tot['maxaway']=max(tot['maxaway'],int((ea-ec).max()))
            tot['bits'][0]+=sum(cond_entropy_bits(v[4]) for v in oa.values()); tot['bits'][1]+=sum(cond_entropy_bits(v[4]) for v in ou.values())
        print(f"{nm} kap={kap} bpp={tot['bits'][1]/(W*H):.3f} samples changed by legality={tot['cl']} (unconstrained oob {tot['oobU']}) toward_src={tot['tow']} away_src={tot['away']} worse_than_clip={tot['awayclip']} max_excess_vs_clip={tot['maxaway']} bits legal/unconstrained={tot['bits'][0]/max(tot['bits'][1],1):.4f} bpp legal/unc {tot['bits'][0]/(W*H):.3f}/{tot['bits'][1]/(W*H):.3f} MSE(all planes) legal/clip {se[0]:.3g}/{se[1]:.3g}",flush=True)

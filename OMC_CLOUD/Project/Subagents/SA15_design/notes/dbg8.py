import numpy as np, cpp2, seq2
from common import cond_entropy_bits
from t2v import gains, field
P=seq2.read('/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/ext_10_422_l0.yuv',512,128,1)
p=P[0]; g=gains(p.shape); T=cpp2.analysis(p,5,2); Df=field({k:v.shape for k,v in T.items()},64,g)
A,oa=cpp2.code_plane(T,None,Df,None,0,1023,5,2,None,None)
U,ou=cpp2.code_plane(T,None,Df,None,-10**7,10**7,5,2,None,None,mid=512)
for k in oa:
    a=oa[k][4]; u=ou[k][4]
    print(k,'bits legal/unc',round(cond_entropy_bits(a)),round(cond_entropy_bits(u)),'symbols differ',int((a!=u).sum()),'mean|q| legal/unc',round(np.abs(a).mean(),3),round(np.abs(u).mean(),3))
a=oa[('HL',0)][4]; u=ou[('HL',0)][4]; d=np.where(a!=u)
print('legal',a[d][:20]); print('unc  ',u[d][:20]); print('D',Df[('HL',0)][d[0][:3]].ravel())
w=oa[('HL',0)][5]; print('w',w[d][:20])
print('hist legal nonzero',np.unique(a[a!=0],return_counts=True))

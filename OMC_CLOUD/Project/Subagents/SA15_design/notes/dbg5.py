import numpy as np, seq2
tabs=seq2.Tables(); A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv'
B=0.5*1280*4; c=seq2.Codec(1280,720,S=4,tabs=tabs)
for t in range(5):
    f=seq2.read(A,1280,720,t); y=c.encode(f,B); e=np.abs(y[0]-f[0])
    rows=e.mean(1); bad=np.where(rows>20)[0]
    print(t,'Y mae',e.mean().round(2),'bad rows',len(bad),bad[:10],'kap at bad slices',[c.frame_info['kap'][r//4] for r in bad[:5]],'refresh',c.frame_info['refresh'])
    if len(bad):
        r=bad[0]; print('   row',r,'err cols max',e[r].max(),'mean dec',y[0][r].mean().round(1),'src',f[0][r].mean().round(1))

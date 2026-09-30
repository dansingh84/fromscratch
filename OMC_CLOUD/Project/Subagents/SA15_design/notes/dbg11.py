import os; os.environ['TABLES']='../out/tables_B.pkl'
import numpy as np, seq2
F='../out/r2/floor720_lanczos.yuv'; W,H=1280,720
c=seq2.Codec(W,H,S=4,tabs=seq2.Tables(),rho=0.25)
for t in range(3):
    fr=seq2.read(F,W,H,t); y=c.encode(fr,0.5*W*4); fi=c.frame_info
    e=(y[0]-fr[0]).astype(float); rows=np.sqrt((e**2).mean(1))
    bad=np.where(rows>20)[0]
    print(t,'refresh',fi['refresh'],'rms by 64-row band',np.round([rows[i:i+64].mean() for i in range(0,H,64)],1),'kap',fi['kap'][:12],'bad rows',bad[:5],len(bad))

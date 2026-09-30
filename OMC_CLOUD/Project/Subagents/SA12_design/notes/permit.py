import sys, os, math, numpy as np
os.environ['HF_FAST']='1'; sys.path.insert(0,'.')
import hf
def hp(p):
    q=np.pad(p,1,mode='edge'); return p-sum(q[i:i+p.shape[0],j:j+p.shape[1]] for i in range(3) for j in range(3))/9.0
def per(m,N=128):
    vs=[]
    for r in range(0,m.shape[0]-N+1,N):
        for c in range(0,m.shape[1]-N+1,N):
            t=m[r:r+N,c:c+N]
            if t.std()<1e-6: continue
            S=np.abs(np.fft.fftshift(np.fft.fft2(t-t.mean()))); S[N//2-2:N//2+3,N//2-2:N//2+3]=0; vs.append(S.max()/S.mean())
    return float(np.median(vs))
def code(P,Qf,kV,nv,cscale):
    H,W=P.shape; Hp=-(-H//16)*16; X=np.vstack([P,np.repeat(P[-1:],Hp-H,0)]).astype(np.int64).reshape(-1,16,W)
    w=hf.weights(16,W,5,nv,'s10',kV); ks=hf.keys(5,nv); w[ks[-1]]*=4.0
    st={k:max(1,int(round(2.0**round(Qf-0.5*math.log2(w[k]))))) for k in ks}
    for k in ks:
        if k[0]==1 and k[1] in ('LH','HH'): st[k]=max(1,int(st[k]*cscale))
    LO=np.zeros(X.shape,np.int64); HI=np.full(X.shape,1023,np.int64)
    C=hf.Coder('enc',st); R=hf.run_coder(C,X,LO,HI,5,nv,'s10',kV,True)
    return sum(hf.ent(C.Q[k]) for k in ks), R.reshape(Hp,W)[:H]
if __name__ == "__main__":
    path,fr=sys.argv[1],int(sys.argv[2])
    src=hf.load(path,1920,1080,fr,"422")
    for name,kV,nv,cs in (('B5',"s6a",3,1.0),('B5_s10a',"s10a",3,1.0),('B5_c1half',"s6a",3,0.5)):
        for Qf in (5.5,6.0):
            tb=0; out=[]
            for pi,P in enumerate(src):
                b,R=code(P,Qf,kV,nv,cs if pi>0 else 1.0); tb+=b
                mse=float(((R-P)**2).mean()); out.append('%s psnr %.2f PER %.2f'%('YUV'[pi],10*math.log10(1023**2/mse),per(hp(R.astype(float)))/per(hp(P.astype(float)))))
            print(name,Qf,'bpp %.3f'%(tb/src[0].size),' | '.join(out),flush=True)
    
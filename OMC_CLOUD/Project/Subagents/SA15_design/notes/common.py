import numpy as np
ARMS='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
CELLS={'dng720':(ARMS+'dng_1280x720_422_10.yuv',1280,720),
       'spot':(ARMS+'long/spotrobotL_1920x1080_422_10.yuv',1920,1080),
       'dng1080':(ARMS+'dng_1920x1080_422_10.yuv',1920,1080),
       'floor':(ARMS+'long/floorballgameL_1920x1080_422_10.yuv',1920,1080),
       'hwy':(ARMS+'long/highwaydriveL_1920x1080_422_10.yuv',1920,1080),
       'volley':(ARMS+'long/volleyballgameL_1920x1080_422_10.yuv',1920,1080),
       'gfx':(ARMS+'cf_gfx_448x256_422_10.yuv',448,256)}
def read_frame(path,W,H,f,fmt=422):
    cw=W//2 if fmt in (422,420) else W; ch=H//2 if fmt==420 else H
    n=W*H+2*cw*ch
    a=np.fromfile(path,dtype='<u2',count=n,offset=2*n*f).astype(np.int64)
    Y=a[:W*H].reshape(H,W); Cb=a[W*H:W*H+cw*ch].reshape(ch,cw); Cr=a[W*H+cw*ch:].reshape(ch,cw)
    return [Y,Cb,Cr]
def psnr(a,b,peak=1023):
    m=np.mean((a.astype(np.float64)-b)**2); return 99.0 if m==0 else 10*np.log10(peak*peak/m)
def cond_entropy_bits(q):
    """bits for index array q (2-D) under a causal context model (left,up magnitude classes)."""
    q=np.asarray(q); a=np.minimum(np.abs(q),2)
    L=np.zeros_like(a); L[:,1:]=a[:,:-1]; U=np.zeros_like(a); U[1:,:]=a[:-1,:]
    ctx=(L+3*U).ravel(); s=np.clip(q,-40,40).ravel()+40
    esc=np.abs(q.ravel())>40
    bits=0.0
    for c in range(9):
        m=ctx==c
        if not m.any(): continue
        cnt=np.bincount(s[m],minlength=81).astype(np.float64); p=cnt[cnt>0]/cnt.sum()
        bits+= -(cnt[cnt>0]*np.log2(p)).sum()
    bits+= esc.sum()*12
    return bits

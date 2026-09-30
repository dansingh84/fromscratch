# still background (dng1080 frame 0, repeated) with a moving picture-in-picture (floorballgameL) in the middle
import seq2
A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
def make(a):
    bg=seq2.read(A+'dng_1920x1080_422_10.yuv',1920,1080,0); out=[]
    for t in range(a.N):
        m=seq2.read(A+'long/floorballgameL_1920x1080_422_10.yuv',1920,1080,t); fr=[]
        for pi,(b,x) in enumerate(zip(bg,m)):
            c=b.copy(); sx=2 if pi else 1
            c[272:808,480//sx:1440//sx]=x[272:808,480//sx:1440//sx]; fr.append(c)
        out.append(fr)
    return out

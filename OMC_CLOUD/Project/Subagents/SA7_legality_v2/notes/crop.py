import sys, numpy as np
src,dst,W,Hc,Hd,nf = sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),int(sys.argv[6])
Wc=W//2; fwc=W*Hc+2*Wc*Hc
a=np.fromfile(src,dtype=np.uint16)
out=open(dst,'wb')
for f in range(nf):
    fr=a[f*fwc:(f+1)*fwc]
    if fr.size<fwc: break
    Y=fr[:W*Hc].reshape(Hc,W)[:Hd]; U=fr[W*Hc:W*Hc+Wc*Hc].reshape(Hc,Wc)[:Hd]; V=fr[W*Hc+Wc*Hc:].reshape(Hc,Wc)[:Hd]
    Y.tofile(out); U.tofile(out); V.tofile(out)
out.close()

# A5 one-way: packet loss (a slice's bytes zeroed) + bit-metered background refresh sweep; decoder simulation
import os, sys, numpy as np, seq2
from common import psnr
src,W,H,bpp,N,lf,lslice,rho,tag=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),float(sys.argv[4]),int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]),float(sys.argv[8]),sys.argv[9]
S=int(os.environ.get('S','8')); tabs=seq2.Tables(); cod=seq2.Codec(W,H,S=S,tabs=tabs,rho=rho); dec=seq2.Decoder(cod); ref=seq2.Decoder(cod)
nsrc=24
for t in range(N):
    k=t%(2*nsrc-2); fidx=k if k<nsrc else 2*nsrc-2-k        # ping-pong to extend the 24-frame arm
    fr=seq2.read(src,W,H,fidx)
    y=cod.encode(fr,bpp*W*S); fi=cod.frame_info
    lost=(lslice*S,(lslice+1)*S) if t==lf else None
    yd=dec.decode(fi,lost); yr=ref.decode(fi,None)
    assert all((a==b).all() for a,b in zip(yr,y)), 'clean decoder != encoder'
    dif=[(a!=b) for a,b in zip(yd,y)]; rows=np.where(dif[0].any(1)|np.repeat(dif[1].any(1),1)|dif[2].any(1))[0]
    ps=[psnr(a,b) for a,b in zip(fr,yd)]
    print(f'{tag} t={t} src_f={fidx} refresh_rows={fi["refresh"]} front={cod.front} damaged samples Y/Cb/Cr={[int(d.sum()) for d in dif]} rows={(int(rows.min()),int(rows.max())) if len(rows) else None} psnr(dec)={ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f} bpp={(fi["bits"].sum()+fi["vbits"])/(W*H):.3f}',flush=True)

#!/usr/bin/env python3
"""texstat.py - TEXTURE-STATISTIC FIDELITY, per plane.

Built 2026-09-03 because the owner's eye caught two things flatplane's block
count did not: (a) the shipped codec has visible chroma flatness where
flatplane reported 0.17%, and (b) both the shipped codec and the best arm carry
a faint REGULAR pattern the source does not have (the grain fill's fixed tile).

flatplane counts blocks that fell below a threshold. It cannot see texture that
is present but WRONG - too weak, or periodic. Two numbers per plane:

  AMP  = std(hp(decode)) / std(hp(source))     1.00 = same texture energy
                                               <1  = washed out, >1 = invented
  PER  = spectral peak / mean of hp(decode), over hp(source)'s own value.
         1.00 = as aperiodic as the source; >1 = a repeating structure the
         source does not have (a tile, a dither, a stipple).
  COR  = corr(hp(decode), hp(source)) over TEXTURED blocks only.
         THE ADVERSARIAL TERM, added 2026-09-03 against my own claim.  AMP and
         flatplane both reward a codec for having texture, not for having the
         RIGHT texture, so a synthetic-grain codec scores well on both by
         construction.  COR asks whether the texture that is there is the
         source's own: 1.00 = the real detail, 0.00 = plausible noise that
         happens to have the right energy.  A high AMP with a low COR is
         invention, not preservation, and must be reported as such.

  DO NOT USE AMP AS A BACKSTOP FOR THE ARTIFACT.  Measured by Agent 3 on a
  blinded sweep: AMP stayed within ~7% of unity (0.968-1.075) across the WHOLE
  range while COR fell monotonically 0.754 -> 0.612 and smudge groups climbed
  4 -> 66.  AMP was flat while the artifact grew by an order of magnitude.
  COR is the column that stayed monotone.  And do not set a threshold on AMP:
  measured on dng 4:2:2 10-bit chroma, OMC AMP=1.130 COR=0.103 against
  XS AMP=0.497 COR=0.414 -- an AMP threshold scores the INVENTING arm better
  than the honest one.  Report AMP and COR side by side; classify on COR.

Both are computed on the high-pass residual so they describe TEXTURE, not level.
usage: texstat.py src.yuv dec.yuv W H frame [--fmt 422] [--depth 10]
"""
import sys, numpy as np
a=sys.argv[1:]; fmt,dep='422',10
for k in ('--fmt','--depth'):
    if k in a:
        i=a.index(k); v=a[i+1]; del a[i:i+2]
        fmt = v if k=='--fmt' else fmt; dep = int(v) if k=='--depth' else dep
src,dec,W,H,F=a[0],a[1],int(a[2]),int(a[3]),int(a[4])
Wc=W//2 if fmt=='422' else W; fw=W*H+2*Wc*H
def planes(p):
    d=np.fromfile(p,dtype=np.uint16)[F*fw:(F+1)*fw].astype(np.float64)
    return d[:W*H].reshape(H,W),d[W*H:W*H+Wc*H].reshape(H,Wc),d[W*H+Wc*H:].reshape(H,Wc)
def hp(p):
    q=np.pad(p,1,mode='edge')
    box=(q[:-2,:-2]+q[:-2,1:-1]+q[:-2,2:]+q[1:-1,:-2]+q[1:-1,1:-1]+q[1:-1,2:]
         +q[2:,:-2]+q[2:,1:-1]+q[2:,2:])/9.0
    return p-box
def per(m,N=128):
    """peak-to-mean of the 2-D spectrum, averaged over N-sized tiles, DC excluded"""
    h,w=m.shape; vs=[]
    for r in range(0,h-N+1,N):
        for c in range(0,w-N+1,N):
            t=m[r:r+N,c:c+N]
            if t.std()<1e-6: continue
            S=np.abs(np.fft.fftshift(np.fft.fft2(t-t.mean())))
            S[N//2-2:N//2+3,N//2-2:N//2+3]=0
            vs.append(S.max()/S.mean())
    return float(np.median(vs)) if vs else float('nan')
def bl(x,b=16):
    nh,nw=x.shape[0]//b,x.shape[1]//b
    return x[:nh*b,:nw*b].reshape(nh,b,nw,b).mean(axis=(1,3))
sp=planes(src); dp=planes(dec); out=[]
for s,d,nm in zip(sp,dp,('Y','Cb','Cr')):
    hs,hd=hp(s),hp(d)
    amp=hd.std()/max(hs.std(),1e-9)
    # COR over textured blocks only -- the same "textured" test flatplane uses
    B=16; E=bl(np.abs(hs),B); med=np.median(E); tex=E>0.5*med
    m=np.repeat(np.repeat(tex,B,0),B,1)
    hs2,hd2=hs[:m.shape[0],:m.shape[1]][m],hd[:m.shape[0],:m.shape[1]][m]
    cor=float(np.corrcoef(hs2,hd2)[0,1]) if hs2.size>8 else float('nan')
    out.append("%s AMP=%.3f PER=%.2f COR=%.3f"%(nm,amp,per(hd)/max(per(hs),1e-9),cor))
print("TEXSTAT "+"  ".join(out))

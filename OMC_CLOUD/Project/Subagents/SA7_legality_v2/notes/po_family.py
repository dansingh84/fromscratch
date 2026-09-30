#!/usr/bin/env python3
"""[SA7] DESIGN3 follow-up, source-only. No codec.
The predictor family  P_w = [w*a + (8-w)*b + (8-w)*c + w*d] / 16  over the four even neighbours.
  w = -1 : the shipped (9,7)-M predict (NON-convex: negative outer taps)
  w =  0 : the two-tap 5/3 predict (convex, DESIGN3 as written)
  w >  0 : convex four-tap members;  w = 1 is (1,7,7,1)/16
Convex iff 0 <= w <= 8.  Every symmetric member reproduces constants and linears; only w<0 adds
cubic reproduction, which is exactly the property that costs the negative lobe.
Reports (1) per-band energy and the AM/GM coding-gain proxy for the shipped tree and for
predict-only at several w, (2) the least-squares optimal w* per cell, (3) the LL5 aliasing
signature, (4) cap-binding statistics.
usage: po_family.py SRC W H FRAME DEPTH FMT
"""
import sys, numpy as np
src,W,H,f,dep,fmt = sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),sys.argv[6]
Wc = W if fmt=='444' else W//2
fw = W*H + 2*Wc*H
raw = np.fromfile(src, dtype=np.uint16)
if raw.size < (f+1)*fw: sys.exit("frame %d not present"%f)
fr = raw[f*fw:(f+1)*fw].astype(np.int64)
planes = {'Y': fr[:W*H].reshape(H,W),
          'Cb': fr[W*H:W*H+Wc*H].reshape(H,Wc),
          'Cr': fr[W*H+Wc*H:].reshape(H,Wc)}
maxv = (1<<dep)-1
mid  = 1<<(dep-1)

def ev_od(x, axis):
    x = np.moveaxis(x, axis, 0); n = x.shape[0]//2*2; x = x[:n]
    return x[0::2].copy(), x[1::2].copy()
def nb(e):
    a = np.concatenate([e[1:2], e[:-1]], 0)
    c = np.concatenate([e[1:], e[-1:]], 0)
    d = np.concatenate([e[2:], e[-1:], e[-2:-1]], 0)
    return a, c, d
def predict(e, w):
    a, c, d = nb(e); b = e
    return ((w*(a+d) + (8-w)*(b+c) + 8) >> 4)
def split(x, axis, w, update):
    """w = -1 shipped 9/7-M predict; w >= 0 convex.  update=False -> lowpass is the evens."""
    e, o = ev_od(x, axis)
    dsub = o - predict(e, w)
    if update:
        dm = np.concatenate([dsub[:1], dsub[:-1]], 0)
        s = e + ((dm + dsub + 2)//4)
    else:
        s = e
    return np.moveaxis(s,0,axis), np.moveaxis(dsub,0,axis)
def split53(x, axis, update):   # levels 3-5 and the verticals: always the two-tap
    return split(x, axis, 0, update)

def tree(x, w12, update):
    """anisotropic 2 vertical x 5 horizontal; w12 = the horizontal predictor at levels 1-2."""
    B = {}
    s, B['LH1'] = split53(x, 0, update)
    s, B['HL1'] = split(s, 1, w12, update)
    _, B['HH1'] = split(B['LH1'], 1, w12, update)
    s2, B['LH2'] = split53(s, 0, update)
    s3, B['HL2'] = split(s2, 1, w12, update)
    _, B['HH2'] = split(B['LH2'], 1, w12, update)
    for nm in ('HL3','HL4','HL5'):
        s3, B[nm] = split53(s3, 1, update)
    B['LL5'] = s3
    return B
ORDER = ('LL5','HL5','HL4','HL3','LH2','HL2','HH2','LH1','HL1','HH1')
def stats(B):
    parts = [(k, float((B[k].astype(float)**2).mean()), B[k].size) for k in ORDER]
    N = sum(n for _,_,n in parts)
    am = sum(e*n for _,e,n in parts)/N
    gm = np.exp(sum(n*np.log(max(e,1e-9)) for _,e,n in parts)/N)
    return parts, 10*np.log10(am/gm)
def wstar(x, axis):
    """least-squares optimal w: P = (b+c)/2 + (w/16)*[(a+d)-(b+c)] ; w* = 16 E[uv]/E[v^2]"""
    e, o = ev_od(x, axis); a, c, d = nb(e); b = e
    u = (o - (b+c)/2.0).ravel(); v = ((a+d) - (b+c)).ravel().astype(float)
    den = float((v*v).mean())
    return 16.0*float((u*v).mean())/den if den > 0 else 0.0

print("### %s  %dx%d %s %d-bit  frame %d" % (src.split('/')[-1], W, H, fmt, dep, f))
for pn, P in planes.items():
    X = P - mid
    ref, gref = stats(tree(X, -1, True))                       # shipped
    print("  [%s] shipped(w=-1,update)  gain %.2f dB | " % (pn, gref) +
          " ".join("%s %.0f" % (k, e) for k, e, _ in ref))
    base = {k: e for k, e, _ in ref}
    for w in (0, 1, 2, 3):
        cur, g = stats(tree(X, w, False))
        dl = " ".join("%s %+.0f%%" % (k, 100*(e/base[k]-1) if base[k] > 0 else 0)
                      for k, e, _ in cur if k in ('HL5','HL4','HL3','HL2','LL5'))
        print("       predict-only w=%d      gain %.2f dB | %s" % (w, g, dl))
    print("       least-squares optimal w*: H %.2f  V %.2f   (w<0 wants the negative taps)"
          % (wstar(X, 1), wstar(X, 0)))
    # ---- (2) aliasing signature: high-band energy of the level-5 lowpass ----
    def llhi(Bd):
        L = Bd['LL5'].astype(float)
        hx = np.diff(L, axis=1); hy = np.diff(L, axis=0)
        return ((hx*hx).mean() + (hy*hy).mean())/2.0, (L*L).mean()
    # ---- (3) cap binding from the source ----
    def capbind(x, axis, w, s_):
        e,o = ev_od(x, axis); P = predict(e, w) + mid
        r = (o + mid) - P
        half = 1 << (s_-1)
        up = (P > maxv - half) & (r > 0)
        dn = (P < half) & (r < 0)
        return 100.0*float((up|dn).mean())
    print("       cap binds (%% of odd samples) at step 2^s, level-1 horizontal: " +
          "  ".join("s=%d %.3f%%" % (ss, capbind(X,1,0,ss)) for ss in (4,6,8)))
    h_s, e_s = llhi(tree(X, -1, True))
    h_0, e_0 = llhi(tree(X, 0, False))
    print("       LL5 high-band energy (mean sq first difference): shipped %.0f (%.4f of LL energy)"
          "  predict-only %.0f (%.4f)  ratio %.2fx"
          % (h_s, h_s/max(e_s,1), h_0, h_0/max(e_0,1), h_0/max(h_s,1e-9)))
    if len(sys.argv) > 7:
        from PIL import Image
        for tag, Bd in (('shipped', tree(X,-1,True)), ('po_w0', tree(X,0,False)), ('po_w1', tree(X,1,False))):
            L = Bd['LL5'].astype(float); L = (L - L.min())/max(L.max()-L.min(),1)
            im = (np.clip(L,0,1)*255).astype(np.uint8)
            im = np.repeat(np.repeat(im, 8, 0), 8, 1)          # x8 so the owner can see it
            rgb = np.dstack([im,im,im])
            Image.fromarray(rgb).save("%s_%s_LL5_%s.png" % (sys.argv[7], pn, tag))
            g = rgb.copy(); g[::8,:,1] = 90; g[:,::8,1] = 90
            Image.fromarray(g).save("%s_%s_LL5_%s_grid.png" % (sys.argv[7], pn, tag))
        print("       LL5 renders written: %s_LL5_{shipped,po_w0,po_w1}.png (+_grid), x8 magnified" % sys.argv[7])

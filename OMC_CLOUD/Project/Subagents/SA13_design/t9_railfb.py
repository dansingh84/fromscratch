#!/usr/bin/env python3
"""T9 -- rails with the NORMATIVE K_max = 1 and the lossless-unit fallback (SA13).  Intra, numpy.
Per unit (anchor row / slice interior): REXT, lossy indices, decoder projection with K_max = 1
(extended domain, as T7).  Not converged -> the unit is coded lossless (steps 1, no REXT).
Bits: context entropy (3 neighbour-magnitude classes: left and upper index in the same band),
pooled per band key and mode.  Reports units lossless, bpp lossy-only vs with fallback, and
writes the decoded frame (fallback picture) for renders.
usage: t9_railfb.py SRC W H NF_LIST TAG S D OUT.yuv"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_structure import read_frame, quant, recon, pad_to, LO, HI
from t2_slices import hfwd, hinv, hbands, br_fwd, br_inv, br_gains
from t4_legal import cells

def ctxH(q):                      # q: 2-D index array of one band chunk -> list of (ctx, sym)
    a = np.abs(q); l = np.zeros_like(a); u = np.zeros_like(a)
    l[:, 1:] = a[:, :-1]; u[1:, :] = a[:-1, :]
    m = l + u; c = np.where(m == 0, 0, np.where(m <= 2, 1, 2))
    return c.ravel(), q.ravel()

POOL = {}
def pool(key, q):
    c, s = ctxH(q); POOL.setdefault(key, [[], []]); POOL[key][0].append(c); POOL[key][1].append(s)
def bits_of(pool_):
    tot = 0.0
    for c, s in pool_.values():
        c = np.concatenate(c); s = np.concatenate(s)
        for k in range(3):
            v = s[c == k]
            if v.size:
                _, n = np.unique(v, return_counts=True); p = n / v.size; tot -= (n * np.log2(p)).sum()
    return tot

def ext(v, M): return v + M * (v >= HI) - M * (v <= LO)

def unit(T, Sy, xs, Dm, M, key):
    """returns (picture, lossless?)"""
    u = ext(xs, M); c = T(u); q = quant(c, Dm); w = recon(q, Dm); clo, chi = cells(q, Dm)
    z = Sy(w); top, bot = z >= HI, z <= LO
    for r in range(2):            # round 0 = check, round 1 = the one projection round
        tgt = np.where(top, HI + M, np.where(bot, LO - M, np.clip(z, LO + 1, HI - 1)))
        if (tgt == z).all():
            pool(('lossy', key), q); return np.clip(z, LO, HI), False
        if r == 1: break
        w = np.clip(T(tgt), clo, chi); z = Sy(w)
    POOL_LY.setdefault(key, [[], []]); cc, ss = ctxH(q); POOL_LY[key][0].append(cc); POOL_LY[key][1].append(ss)
    cl = T(xs); pool(('lossless', key), cl)            # lossless: every coefficient sent as is
    return xs.copy(), True

POOL_LY = {}
src, W, H, NFL, tag, S, D, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), [int(v) for v in sys.argv[4].split(',')], sys.argv[5], int(sys.argv[6]), float(sys.argv[7]), sys.argv[8]
g = br_gains(S); M = int(round(D)); nll = 0; nun = 0; frames_out = []
for f in NFL:
    outp = []
    for pl in read_frame(src, W, H, '422', f):
        x = pad_to(pl, S, 32, 0); Hh, Wp = x.shape; rec = np.zeros_like(x)
        Da = np.zeros((1, Wp)); Di = np.zeros((S - 1, Wp))
        for sl, gh in hbands(Wp):
            Da[:, sl] = D / np.sqrt(g['anchor'] * gh)
            for p in range(1, S): Di[p - 1, sl] = D / np.sqrt(g[p] * gh)
        above = None
        for s in range(-1, Hh // S):
            row = x[0:1] if s < 0 else x[s*S+S-1:s*S+S]
            a, ll = unit(hfwd, hinv, row, Da, M, 'A'); nll += ll; nun += 1
            if s < 0: above = a; continue
            r0 = s * S; A0, A1 = ext(above[0], M), ext(a[0], M)
            def T(Y, A0=A0, A1=A1):
                Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1; Z[1:S] = Y
                return hfwd(br_fwd(Z, S)[1:S])
            def Sy(K, A0=A0, A1=A1):
                Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1; Z[1:S] = hinv(K)
                return br_inv(Z, S)[1:S]
            y, ll = unit(T, Sy, x[r0:r0+S-1], Di, M, 'I'); nll += ll; nun += 1
            rec[r0:r0+S-1] = y; rec[r0+S-1] = a[0]; above = a
        outp.append(rec[:pl.shape[0], :pl.shape[1]])
    frames_out.append(outp)
b_fb = bits_of(POOL); b_ly_extra = bits_of(POOL_LY)
b_lossy_only = bits_of({k: v for k, v in POOL.items() if k[0] == 'lossy'}) + b_ly_extra
n = W * H * len(NFL)
print(f'{tag} D={D} units={nun} lossless={nll} bpp lossy-only={b_lossy_only/n:.3f} with-fallback={b_fb/n:.3f}', flush=True)
np.concatenate([np.concatenate([p.ravel() for p in fo]) for fo in frames_out]).astype('<u2').tofile(out)

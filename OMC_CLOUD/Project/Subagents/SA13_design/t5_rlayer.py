#!/usr/bin/env python3
"""T5 -- cost of the fixed-work exactness layer 'clip + re-read + residual' (SA13).  Intra, numpy.

Bracketed slices (as T2 'br').  Per coded unit (anchor row, then interior):
  gen 1:  q1 = Q(T x);  y = clip(S R(q1))                       (the picture = plain clip)
          q* = Q(T y)   (the next encoder's own reading of y)
          r  = y - clip(S R(q*))                                  (pixel residual, lossless)
  emits (q*, r).  Decoder: clip(S R(q*)) + r = y.  Next encoder on y: Q(T y) = q*, same r.
Reports: flips (q* != q1), pixels with r != 0, and bits: entropy of q* (all bands) and of r
(zeroth order over all pixels of the plane, i.e. including the cost of saying 'zero').

usage: t5_rlayer.py SRC W H FMT FRAMES TAG S steps
"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_structure import read_frame, quant, recon, pad_to, H0, LO, HI, psnr
from t2_slices import hfwd, hinv, hbands, br_fwd, br_inv, br_gains

def main():
    src, W, H, fmt, nf, tag, S = sys.argv[1:8]
    W, H, nf, S = int(W), int(H), int(nf), int(S)
    steps = [float(v) for v in sys.argv[8].split(',')]
    g = br_gains(S)
    for D in steps:
        Q = {}; flips = 0; rnz = 0; rvals = []; npx = 0; se = [0.0, 0.0, 0.0]; oob = 0
        for f in range(nf):
            for k, pl in enumerate(read_frame(src, W, H, fmt, f)):
                x = pad_to(pl, S, 32, 0); Hh, Wp = x.shape
                rec = np.zeros_like(x)
                def code(T, Sy, xs, steps_of, key):
                    nonlocal flips, rnz
                    c = T(xs); q1 = np.zeros_like(c); rq = np.zeros_like(c)
                    for sl, Db in steps_of:
                        q1[..., sl] = quant(c[..., sl], Db); rq[..., sl] = recon(q1[..., sl], Db)
                    y = np.clip(Sy(rq), LO, HI)
                    c2 = T(y); q2 = np.zeros_like(c2); rq2 = np.zeros_like(c2)
                    for sl, Db in steps_of:
                        q2[..., sl] = quant(c2[..., sl], Db); rq2[..., sl] = recon(q2[..., sl], Db)
                        Q.setdefault((key, sl.start), []).append(q2[..., sl].ravel())
                    r = y - np.clip(Sy(rq2), LO, HI)
                    flips += int((q2 != q1).sum()); rnz += int((r != 0).sum()); rvals.append(r.ravel())
                    return y
                above = None
                for s in range(-1, Hh // S):
                    row = x[0:1] if s < 0 else x[s * S + S - 1:s * S + S]
                    st = [(sl, D / np.sqrt(g['anchor'] * gh)) for sl, gh in hbands(Wp)]
                    a = code(hfwd, hinv, row, st, 'A')
                    if s < 0:
                        above = a; continue
                    r0 = s * S
                    A0, A1 = above[0], a[0]
                    def T(Y, A0=A0, A1=A1):
                        Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1
                        Z[1:S] = Y; return hfwd(br_fwd(Z, S)[1:S])
                    def Sy(Kx, A0=A0, A1=A1):
                        Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1
                        Z[1:S] = hinv(Kx); return br_inv(Z, S)[1:S]
                    # per-row steps: build (row-slice, band-slice) pairs via a flattened view
                    Yi = x[r0:r0 + S - 1]
                    c = T(Yi); q1 = np.zeros_like(c); rq = np.zeros_like(c); Dm = np.zeros(c.shape)
                    for p in range(1, S):
                        for sl, gh in hbands(Wp):
                            Dm[p - 1, sl] = D / np.sqrt(g[p] * gh)
                    q1 = quant(c, Dm); rq = recon(q1, Dm)
                    y = np.clip(Sy(rq), LO, HI)
                    q2 = quant(T(y), Dm); rq2 = recon(q2, Dm)
                    for p in range(1, S):
                        for sl, gh in hbands(Wp):
                            Q.setdefault((p & -p, sl.start), []).append(q2[p - 1, sl].ravel())
                    r = y - np.clip(Sy(rq2), LO, HI)
                    flips += int((q2 != q1).sum()); rnz += int((r != 0).sum()); rvals.append(r.ravel())
                    rec[r0:r0 + S - 1] = y; rec[r0 + S - 1] = a[0]
                    above = a
                rec = rec[:pl.shape[0], :pl.shape[1]]
                oob += int(((rec < LO) | (rec > HI)).sum())
                se[k] += float(((rec - pl) ** 2).sum()); npx += (pl.size if k == 0 else 0)
                if k == 0: n0 = pl.size
                if k == 1: n1 = pl.size
        bq = sum(H0(np.concatenate(v)) for v in Q.values())
        rv = np.concatenate(rvals); br_ = H0(rv)
        ps = [10 * np.log10(1023 ** 2 / (se[0] / (n0 * nf))), 10 * np.log10(1023 ** 2 / (se[1] / (n1 * nf))),
              10 * np.log10(1023 ** 2 / (se[2] / (n1 * nf)))]
        print(f'{tag} D={D:5.1f} bpp_q={bq/(W*H*nf):.3f} bpp_r={br_/(W*H*nf):.4f} '
              f'(r share {100*br_/(bq+br_):.2f} %) flips={flips} r_nonzero_px={rnz} oob={oob} '
              f'PSNR Y/Cb/Cr {ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f}', flush=True)

if __name__ == '__main__':
    main()

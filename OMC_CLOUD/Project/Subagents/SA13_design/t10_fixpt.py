#!/usr/bin/env python3
"""T10 -- 'emit what the next encoder reads' with REXT (SA13).  Per unit: D = REXT-domain decode with
K projection rounds then clip; gen-1 iterates q_{i+1} = Q(T(REXT(D(q_i)))) until D(q_{i+1}) == D(q_i)
(then q_{i+1} is a fixed point: every later generation reads the same indices).  Reports the number of
iterations per unit (cap 8), bits vs the first q, quality.
usage: t10_fixpt.py SRC W H FMT FRAMES TAG S steps   (env K = projection rounds in D, default 1)"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_structure import read_frame, quant, recon, pad_to, LO, HI, H0
from t2_slices import hfwd, hinv, hbands, br_fwd, br_inv, br_gains
from t4_legal import cells
K = int(os.environ.get('K', '1')); CAPI = 8
def ext(v, M): return v + M * (v >= HI) - M * (v <= LO)
def dec(T, Sy, q, Dm, M):
    w = recon(q, Dm); clo, chi = cells(q, Dm); z = Sy(w); top, bot = z >= HI, z <= LO
    for r in range(K):
        tgt = np.where(top, HI + M, np.where(bot, LO - M, np.clip(z, LO + 1, HI - 1)))
        if (tgt == z).all(): break
        w = np.clip(T(tgt), clo, chi); z = Sy(w)
    return np.clip(z, LO, HI)
def unit(T, Sy, xs, Dm, M, st):
    q = quant(T(ext(xs, M)), Dm); y = dec(T, Sy, q, Dm, M); q0 = q
    for i in range(CAPI + 1):
        q2 = quant(T(ext(y, M)), Dm)
        if (q2 == q).all():                  # already a fixed point: next encoder reads q
            st.append(i); return y, q, q0
        if i == CAPI: st.append(99); return y, q, q0
        y2 = dec(T, Sy, q2, Dm, M); q, y = q2, y2
src, W, H, fmt, fl, tag, S = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], [int(v) for v in sys.argv[5].split(',')], sys.argv[6], int(sys.argv[7])
g = br_gains(S)
for D in [float(v) for v in sys.argv[8].split(',')]:
    M = int(round(D)); st = []; b0 = []; b1 = []; se = np.zeros(3); nn = np.zeros(3)
    for f in fl:
        for k, pl in enumerate(read_frame(src, W, H, fmt, f)):
            x = pad_to(pl, S, 32, 0); Hh, Wp = x.shape; rec = np.zeros_like(x)
            Da = np.zeros((1, Wp)); Di = np.zeros((S - 1, Wp))
            for sl, gh in hbands(Wp):
                Da[:, sl] = D / np.sqrt(g['anchor'] * gh)
                for p in range(1, S): Di[p - 1, sl] = D / np.sqrt(g[p] * gh)
            above = None
            for s in range(-1, Hh // S):
                row = x[0:1] if s < 0 else x[s*S+S-1:s*S+S]
                a, q, q0 = unit(hfwd, hinv, row, Da, M, st); b1.append(q.ravel()); b0.append(q0.ravel())
                if s < 0: above = a; continue
                r0 = s * S; A0, A1 = ext(above[0], M), ext(a[0], M)
                def T(Y, A0=A0, A1=A1):
                    Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1; Z[1:S] = Y
                    return hfwd(br_fwd(Z, S)[1:S])
                def Sy(Kx, A0=A0, A1=A1):
                    Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1; Z[1:S] = hinv(Kx)
                    return br_inv(Z, S)[1:S]
                y, q, q0 = unit(T, Sy, x[r0:r0+S-1], Di, M, st); b1.append(q.ravel()); b0.append(q0.ravel())
                rec[r0:r0+S-1] = y; rec[r0+S-1] = a[0]; above = a
            rec = rec[:pl.shape[0], :pl.shape[1]]; se[k] += ((rec - pl) ** 2).sum(); nn[k] += pl.size
    st = np.array(st); n = W * H * len(fl)
    ps = 10 * np.log10(1023 ** 2 / np.maximum(se / nn, 1e-9))
    print(f'{tag} K={K} D={D} units={len(st)} iters: 0={int((st==0).sum())} 1={int((st==1).sum())} 2={int((st==2).sum())} '
          f'3-8={int(((st>2)&(st<99)).sum())} fail={int((st==99).sum())} | H0 bpp first={H0(np.concatenate(b0))/n:.3f} '
          f'emitted={H0(np.concatenate(b1))/n:.3f} | PSNR {ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f}', flush=True)

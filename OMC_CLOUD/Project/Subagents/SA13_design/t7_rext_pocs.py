#!/usr/bin/env python3
"""T7 -- rail extension + in-cell projection in the EXTENDED domain (SA13).  Intra, numpy.

Encoder (every generation, same rule): u = ext(picture): pixels exactly at a rail are pushed M
outside it.  q = Q(T u).  Decoder: z0 = S R(q); rail set Rset = {z0 >= HI} U {z0 <= LO};
alternating projection between  A = {v : v = HI+M on top rails, LO-M on bottom rails,
LO+1 <= v <= HI-1 elsewhere}  and  B = {v : T v in cells(q)}; output y = clip(v).
The next encoder reads y, rail pixels are exactly the decoder's Rset, ext(y) = v, T v in cells
-> same q.  Reports rounds to converge, rail-set mismatch vs the source, oob, quality.

usage: t7_rext_pocs.py SRC W H FMT FRAMES TAG S steps
"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_structure import read_frame, quant, recon, pad_to, LO, HI
from t2_slices import hfwd, hinv, hbands, br_fwd, br_inv, br_gains
from t4_legal import cells

MM = float(os.environ.get('MM', '1.0')); CAP = int(os.environ.get('CAP', '64'))

def ext(v, M):
    return v + M * (v >= HI) - M * (v <= LO)

def solve(T, Sy, u_src, Dm, M):
    c = T(u_src); q = quant(c, Dm); w = recon(q, Dm); clo, chi = cells(q, Dm)
    z = Sy(w); top = z >= HI; bot = z <= LO
    for r in range(CAP + 1):
        v = Sy(w)
        tgt = np.where(top, HI + M, np.where(bot, LO - M, np.clip(v, LO + 1, HI - 1)))
        if (tgt == v).all():
            return np.clip(v, LO, HI), r, True, top | bot
        if r == CAP:
            return np.clip(v, LO, HI), r, False, top | bot
        w = np.clip(T(tgt), clo, chi)

def main():
    src, W, H, fmt, nf, tag, S = sys.argv[1:8]
    W, H, nf, S = int(W), int(H), int(nf), int(S)
    g = br_gains(S)
    for D in [float(v) for v in sys.argv[8].split(',')]:
        M = int(round(MM * D)); rounds = []; fail = 0; mis = 0; se = np.zeros(3); n = np.zeros(3)
        for f in range(nf):
            for k, pl in enumerate(read_frame(src, W, H, fmt, f)):
                x = pad_to(pl, S, 32, 0); Hh, Wp = x.shape; rec = np.zeros_like(x)
                Da = np.zeros((1, Wp))
                for sl, gh in hbands(Wp): Da[:, sl] = D / np.sqrt(g['anchor'] * gh)
                Di = np.zeros((S - 1, Wp))
                for p in range(1, S):
                    for sl, gh in hbands(Wp): Di[p - 1, sl] = D / np.sqrt(g[p] * gh)
                above = None
                for s in range(-1, Hh // S):
                    row = x[0:1] if s < 0 else x[s * S + S - 1:s * S + S]
                    a, rr, ok, rs = solve(hfwd, hinv, ext(row, M), Da, M)
                    rounds.append(rr); fail += (not ok); mis += int((rs != ((row >= HI) | (row <= LO))).sum())
                    if s < 0: above = a; continue
                    r0 = s * S; A0, A1 = ext(above[0], M), ext(a[0], M)
                    def T(Y, A0=A0, A1=A1):
                        Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1
                        Z[1:S] = Y; return hfwd(br_fwd(Z, S)[1:S])
                    def Sy(K, A0=A0, A1=A1):
                        Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1
                        Z[1:S] = hinv(K); return br_inv(Z, S)[1:S]
                    Yi = x[r0:r0 + S - 1]
                    y, rr, ok, rs = solve(T, Sy, ext(Yi, M), Di, M)
                    rounds.append(rr); fail += (not ok); mis += int((rs != ((Yi >= HI) | (Yi <= LO))).sum())
                    rec[r0:r0 + S - 1] = y; rec[r0 + S - 1] = a[0]; above = a
                rec = rec[:pl.shape[0], :pl.shape[1]]
                se[k] += float(((rec - pl) ** 2).sum()); n[k] += pl.size
        rounds = np.array(rounds)
        ps = 10 * np.log10(1023 ** 2 / (se / n))
        print(f'{tag} M={M} D={D:5.1f} units={len(rounds)} need>0={int((rounds>0).sum())} '
              f'max={rounds.max()} >2={int((rounds>2).sum())} >4={int((rounds>4).sum())} >8={int((rounds>8).sum())} '
              f'unconverged@{CAP}={fail} railset_mismatch={mis} PSNR Y/Cb/Cr {ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f}', flush=True)

if __name__ == '__main__':
    main()

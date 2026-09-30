#!/usr/bin/env python3
"""T4 -- in-cell legalisation cost on the bracketed structure (SA13).  Intra, numpy.

For each slice: (1) anchor row = 1-D horizontal 5/3 (5 levels); (2) interior = bracketed vertical
5/3 between the (legal, final) anchors + 5 horizontal levels.  Quantise with the T2 steps.
Legaliser = alternating projection: synthesise -> clip -> analyse -> clamp into cells, until the
synthesis is legal (then the picture is legal AND every coefficient is in its own cell, which is
what makes the next encoder re-derive the same indices).  Counts rounds per problem.
Variant 'cf' (coarse-first): each round the correction is applied level by level coarse -> fine
(horizontal LL first, then each finer horizontal band), re-synthesising between levels.

usage: t4_legal.py SRC W H FMT FRAMES TAG S steps
"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_structure import read_frame, quant, recon, pad_to, LO, HI
from t2_slices import hfwd, hinv, hbands, br_fwd, br_inv, br_gains

CAP = 200

def cells(q, Db):
    a = np.abs(q); c = np.ceil
    lo_m = np.where(a == 0, -(c(Db) - 1), c(a * Db))
    hi_m = np.where(a == 0, c(Db) - 1, c((a + 1) * Db) - 1)
    lo = np.where(q < 0, -hi_m, lo_m); hi = np.where(q < 0, -lo_m, hi_m)
    lo = np.where(a == 0, -(c(Db) - 1), lo); hi = np.where(a == 0, c(Db) - 1, hi)
    return lo.astype(np.int64), hi.astype(np.int64)

def legalise(w, clo, chi, synth, anal, mode, bandslices=None):
    """returns (final coefficients, rounds, legal?)"""
    for r in range(CAP + 1):
        y = synth(w)
        bad = (y < LO) | (y > HI)
        if not bad.any():
            return w, r, True
        if r == CAP:
            return w, r, False
        if mode == 'pocs':
            w = np.clip(anal(np.clip(y, LO, HI)), clo, chi)
        else:   # coarse-first: apply the correction band by band, coarse -> fine
            for sl in bandslices:
                y = synth(w)
                t = np.clip(anal(np.clip(y, LO, HI)), clo, chi)
                w = w.copy(); w[..., sl] = t[..., sl]
    return w, CAP, False

def main():
    src, W, H, fmt, nf, tag, S = sys.argv[1:8]
    W, H, nf, S = int(W), int(H), int(nf), int(S)
    steps = [float(v) for v in sys.argv[8].split(',')]
    g = br_gains(S)
    for mode in ('pocs', 'cf'):
        for D in steps:
            stats = {'anch': [], 'int': []}; pre = 0; fail = 0
            for f in range(nf):
                for pl in read_frame(src, W, H, fmt, f):
                    x = pad_to(pl, S, 32, 0); Hh, Wp = x.shape
                    hb = [sl for sl, _ in hbands(Wp)][::-1]      # LL first
                    above = None
                    for s in range(-1, Hh // S):
                        row = x[0:1] if s < 0 else x[s * S + S - 1:s * S + S]
                        c = hfwd(row); cq = np.zeros_like(c); clo = np.zeros_like(c); chi = np.zeros_like(c)
                        for sl, gh in hbands(Wp):
                            Db = D / np.sqrt(g['anchor'] * gh)
                            q = quant(c[:, sl], Db); cq[:, sl] = recon(q, Db)
                            clo[:, sl], chi[:, sl] = cells(q, Db)
                        pre += int(((hinv(cq) < LO) | (hinv(cq) > HI)).sum())
                        w, rr, ok = legalise(cq, clo, chi, hinv, hfwd, mode, hb)
                        stats['anch'].append(rr); fail += (not ok)
                        a = np.clip(hinv(w), LO, HI)
                        if s < 0:
                            above = a; continue
                        r0 = s * S
                        X = np.zeros((S + 1, Wp), dtype=np.int64)
                        X[0] = above[0]; X[S] = a[0]; X[1:S] = x[r0:r0 + S - 1]
                        C = br_fwd(X, S)
                        K = hfwd(C[1:S]); Kq = np.zeros_like(K); klo = np.zeros_like(K); khi = np.zeros_like(K)
                        for p in range(1, S):
                            for sl, gh in hbands(Wp):
                                Db = D / np.sqrt(g[p] * gh)
                                q = quant(K[p - 1:p, sl], Db); Kq[p - 1:p, sl] = recon(q, Db)
                                klo[p - 1:p, sl], khi[p - 1:p, sl] = cells(q, Db)
                        def synth(Kx, A0=above[0], A1=a[0]):
                            Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1
                            Z[1:S] = hinv(Kx); return br_inv(Z, S)[1:S]
                        def anal(Y, A0=above[0], A1=a[0]):
                            Z = np.zeros((S + 1, Wp), dtype=np.int64); Z[0] = A0; Z[S] = A1
                            Z[1:S] = Y; return hfwd(br_fwd(Z, S)[1:S])
                        pre += int(((synth(Kq) < LO) | (synth(Kq) > HI)).sum())
                        w, rr, ok = legalise(Kq, klo, khi, synth, anal, mode, hb)
                        stats['int'].append(rr); fail += (not ok)
                        above = a
            out = []
            for k, v in stats.items():
                v = np.array(v)
                out.append(f'{k}: n={len(v)} need>0={int((v>0).sum())} max={v.max()} '
                           f'p99={np.percentile(v,99):.0f} >4={int((v>4).sum())} >16={int((v>16).sum())}')
            print(f'{tag} {mode:4s} D={D:5.1f} oob_pre={pre} unconverged@{CAP}={fail} | ' + ' | '.join(out), flush=True)

if __name__ == '__main__':
    main()

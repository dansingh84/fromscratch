#!/usr/bin/env python3
"""SA12 experiment TP: temporal prediction inside the legal HF pyramid (variant B: 2/10 horizontal, 2/6 vertical,
independent 16-row slices, 2 vertical + 3 horizontal-only levels).  Frame f0 intra -> reference y0; frame f1 coded with
in-band prediction  d_pred = P_spatial(s_rec) + alpha*(d_ref - P_spatial(s_ref))  (LL: alpha*LL_ref; HL/H: alpha*e_ref),
reference bands from the forward S-transform of the motion-compensated reference y0.
Vector modes:  intra (alpha=0) | zero | oracle (8x8 source full search +-R, all levels, vector bits NOT counted) |
derived (decoder-side: level-2 vectors from the decoded level-2 lowpass of the current frame, 16x16 blocks, +-R;
level-1 vectors refined +-2 px from the decoded level-1 lowpass, 8x8 blocks; coarser levels zero).  Legality boxes,
closed loop, K-rule, gen-2 check as hf.py.  Luma vectors drive chroma (horizontal /2 at 4:2:2)."""
import numpy as np, sys, math, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hf
from hf import fd, hsplit, vsplit, hmerge, vmerge, pred, vpred, dint, Coder

def shift(img, dy, dx):
    H, W = img.shape
    ys = np.clip(np.arange(H) + dy, 0, H - 1); xs = np.clip(np.arange(W) + dx, 0, W - 1)
    return img[ys][:, xs]

def lowpass(img, lev):      # frame-level S lowpass (H then V per level), all levels 2-D here (lev <= 2)
    A = img[None]
    for _ in range(lev):
        Lc, _ = hsplit(A); A, _ = vsplit(Lc)
    return A[0]

def mc(ref, V, bs):          # V (nby, nbx, 2) integer vectors per bs x bs block
    H, W = ref.shape; out = np.empty_like(ref)
    for by in range(V.shape[0]):
        for bx in range(V.shape[1]):
            dy, dx = V[by, bx]; y0, x0 = by * bs, bx * bs
            ys = np.clip(np.arange(y0, min(y0 + bs, H)) + dy, 0, H - 1); xs = np.clip(np.arange(x0, min(x0 + bs, W)) + dx, 0, W - 1)
            out[y0:y0 + bs, x0:x0 + bs] = ref[ys][:, xs]
    return out

def search(cur, ref, bs, R, center=None, lev=0, step=1):
    """block SAD search of cur (level-lev lowpass of the current frame, H/2^lev x W/2^lev) against the level-lev
    lowpass of ref shifted by v (pixels); blocks bs x bs in the lowpass domain; canonical tie-break."""
    h, w = cur.shape; nby, nbx = h // bs, w // bs
    best = np.full((nby, nbx), np.inf); V = np.zeros((nby, nbx, 2), np.int64)
    cands = sorted([(dy, dx) for dy in range(-R, R + 1, step) for dx in range(-R, R + 1, step)], key=lambda v: (abs(v[0]) + abs(v[1]), v))
    for dy, dx in cands:
        if center is None:
            L = lowpass(shift(ref, dy, dx), lev) if lev else shift(ref, dy, dx)
            sad = np.abs(cur[:nby * bs, :nbx * bs] - L[:nby * bs, :nbx * bs]).reshape(nby, bs, nbx, bs).sum((1, 3))
            m = sad < best; best[m] = sad[m]; V[m] = (dy, dx)
        else:
            pass
    return V

def refine(cur, ref, bs, Vc, cbs, R, lev):
    """per block (bs in lowpass domain) search +-R px around the coarse vector of the enclosing coarse block;
    vectorised: one pass over the union of candidate vectors, canonical tie-break (smaller |dv|, then raster)."""
    h, w = cur.shape; nby, nbx = h // bs, w // bs
    ratio = cbs // bs
    base = np.repeat(np.repeat(Vc, ratio, 0), ratio, 1)[:nby, :nbx]
    best = np.full((nby, nbx), np.inf); bestk = np.full((nby, nbx), 10 ** 9); V = base.copy()
    lo_y, hi_y = base[..., 0].min() - R, base[..., 0].max() + R
    lo_x, hi_x = base[..., 1].min() - R, base[..., 1].max() + R
    for dy in range(lo_y, hi_y + 1):
        for dx in range(lo_x, hi_x + 1):
            ddy = dy - base[..., 0]; ddx = dx - base[..., 1]
            ok = (np.abs(ddy) <= R) & (np.abs(ddx) <= R)
            if not ok.any(): continue
            L = lowpass(shift(ref, dy, dx), lev)
            sad = np.abs(cur[:nby * bs, :nbx * bs] - L[:nby * bs, :nbx * bs]).reshape(nby, bs, nbx, bs).sum((1, 3))
            key = (np.abs(ddy) + np.abs(ddx)) * 10000 + (ddy + R) * 100 + (ddx + R)
            m = ok & ((sad < best) | ((sad == best) & (key < bestk)))
            best[m] = sad[m]; bestk[m] = key[m]; V[m] = (dy, dx)
    return V

def ref_bands(M, sh):
    """forward S pyramid of a motion-compensated reference frame M (H x W), per slice; returns per-level band refs."""
    H, W = M.shape; X = M.reshape(H // sh, sh, W); out = {}; A = X
    for lev in range(1, 6):
        Lc, dH = hsplit(A)
        if lev <= 2:
            LL, dL = vsplit(Lc); e = dH - pred(Lc, 's10'); HL, dE = vsplit(e)
            out[lev] = dict(LL=LL, dL=dL, HL=HL, dE=dE, Lc=Lc); A = LL
        else:
            e = dH - pred(Lc, 's10'); out[lev] = dict(Lc=Lc, e=e); A = Lc
    out[6] = dict(LL=A); return out

def rec_t(C, lev, A, Alo, Ahi, RB, alpha, hooks):
    kH, kV = 's10', 's6'
    if lev > 5:
        p = alpha * RB[6]['LL'] if RB else 0
        return C.qc((lev, 'LL'), A - p, Alo - p, Ahi - p) + p
    Lc_s, dH_s = hsplit(A); Llo, _ = hsplit(Alo); Lhi, _ = hsplit(Ahi)
    if lev <= 2:
        LL_s, dL_s = vsplit(Lc_s); LLlo, _ = vsplit(Llo); LLhi, _ = vsplit(Lhi)
        LL = rec_t(C, lev + 1, LL_s, LLlo, LLhi, RB, alpha, hooks)
        R = hooks(lev, LL) if hooks else RB          # decoder-side vector derivation point (after LL of this level is final)
        r = R[lev] if R else None
        p = vpred(LL, kV, None) + (alpha * (r['dL'] - vpred(r['LL'], kV, None)) if r else 0)
        lo, hi = dint(LL, Llo[:, 0::2], Lhi[:, 0::2], Llo[:, 1::2], Lhi[:, 1::2], hf.rv(LL.shape))
        dL = C.qc((lev, 'LH'), dL_s - p, lo - p, hi - p) + p
        Lc = vmerge(LL, dL)
    else:
        Lc = rec_t(C, lev + 1, Lc_s, Llo, Lhi, RB, alpha, hooks); r = RB[lev] if RB else None; R = RB
    pH = pred(Lc, kH)
    hlo, hhi = dint(Lc, Alo[..., 0::2], Ahi[..., 0::2], Alo[..., 1::2], Ahi[..., 1::2], hf.rh(Lc.shape))
    elo, ehi = hlo - pH, hhi - pH; e_s = dH_s - pH
    if lev <= 2:
        HL_s, dE_s = vsplit(e_s); HLlo, _ = vsplit(elo); HLhi, _ = vsplit(ehi)
        ph = alpha * r['HL'] if r else 0
        HL = C.qc((lev, 'HL'), HL_s - ph, HLlo - ph, HLhi - ph) + ph
        p2 = vpred(HL, kV, None) + (alpha * (r['dE'] - vpred(r['HL'], kV, None)) if r else 0)
        lo2, hi2 = dint(HL, elo[:, 0::2], ehi[:, 0::2], elo[:, 1::2], ehi[:, 1::2], hf.rv(HL.shape))
        dE = C.qc((lev, 'HH'), dE_s - p2, lo2 - p2, hi2 - p2) + p2
        e = vmerge(HL, dE)
    else:
        pe = alpha * r['e'] if r else 0
        e = C.qc((lev, 'H'), e_s - pe, elo - pe, ehi - pe) + pe
    return hmerge(Lc, e + pH)

def code_frame(planes, refs, mode, Qf, sh, lo, hi, depth, R=16, src_vec=None, wc={}):
    """returns bits, psnr per plane, oor, gen2-exact, recon planes"""
    kll = -1; tot = 0.0; ps = []; oor = 0; ex = True; recs = []
    Vs = {}; V2s = {}
    for pi, P in enumerate(planes):
        H, W = P.shape; X = P.astype(np.int64).reshape(H // sh, sh, W)
        wk = (sh, W)
        if wk not in wc: wc[wk] = hf.weights(sh, W, 5, 2, 's10', 's6')
        w = dict(wc[wk]); ks = hf.keys(5, 2); w[ks[-1]] *= 4.0 ** (-kll)
        steps = {k: max(1, int(round(2.0 ** round(Qf - 0.5 * math.log2(w[k]))))) for k in ks}
        LO = np.full(X.shape, lo, np.int64); HI = np.full(X.shape, hi, np.int64)
        cx = 1 if W == planes[0].shape[1] else planes[0].shape[1] // W
        def vec_scale(V): V = V.copy(); V[..., 1] = fd(V[..., 1], cx); return V
        ref = refs[pi] if refs is not None else None
        def run(Xin, Vstore):
            if mode == 'intra' or ref is None:
                C = Coder('enc', steps); return C, hf.rec_level(C, 1, 5, 2, Xin, LO, HI, 's10', 's6', None)
            if mode == 'zero':
                RB = ref_bands(ref, sh); C = Coder('enc', steps); return C, rec_t(C, 1, Xin, LO, HI, RB, 1, None)
            if mode == 'oracle':
                RB = ref_bands(mc(ref, vec_scale(src_vec), 8 if cx == 1 else 8), sh)
                C = Coder('enc', steps); return C, rec_t(C, 1, Xin, LO, HI, RB, 1, None)
            # derived: coarse levels zero motion; hooks derive vectors from the decoded lowpass
            RB0 = ref_bands(ref, sh)
            def hooks(lev, LL):
                cur = LL.reshape(-1, LL.shape[-1])          # frame-level lowpass at this level (slices stacked)
                if pi == 0:
                    if lev == 2: Vstore[2] = search(cur, ref, 4, R, lev=2)
                    if lev == 1: Vstore[1] = refine(cur, ref, 4, Vstore[2], 8, 2, 1)
                V = vec_scale(Vstore[lev]); bs = (4 << lev)
                return ref_bands(mc(ref, V, bs), sh) if True else None
            C = Coder('enc', steps); return C, rec_t(C, 1, Xin, LO, HI, RB0, 1, hooks)
        C, Z = run(X, Vs)
        tot += sum(hf.ent(C.Q[k]) for k in ks)
        Rr = Z.reshape(H, W); oor += int(((Rr < lo) | (Rr > hi)).sum())
        C2, Z2 = run(Rr.reshape(H // sh, sh, W), V2s)
        if mode == 'derived' and pi == 0:
            ex &= all(np.array_equal(V2s[k], Vs[k]) for k in Vs)
        ex &= bool(all(np.array_equal(C2.Q[k], C.Q[k]) for k in ks) and np.array_equal(Z2, Z))
        err = (Rr - P).astype(float); mse = float((err ** 2).mean())
        ps.append(10 * math.log10(float(2 ** depth - 1) ** 2 / mse)); recs.append(Rr)
    return tot / planes[0].size, ps, oor, ex, recs

if __name__ == '__main__':
    path, W, H, f0, sh, tag = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
    Qfs = json.loads(sys.argv[7]); modes = sys.argv[8].split(',') if len(sys.argv) > 8 else ['intra', 'zero', 'oracle', 'derived']
    lo, hi, depth = 0, 1023, 10
    F0 = hf.load(path, W, H, f0, '422'); F1 = hf.load(path, W, H, f0 + 1, '422')
    Hp = -(-H // sh) * sh
    pad = lambda P: np.vstack([P, np.repeat(P[-1:], Hp - P.shape[0], 0)])
    F0 = [pad(p) for p in F0]; F1 = [pad(p) for p in F1]
    out = {}
    for Qf in Qfs:
        b0, p0, o0, e0, refs = code_frame(F0, None, 'intra', Qf, sh, lo, hi, depth)
        # oracle source vectors: 8x8 luma blocks, full search +-16 on source f1 vs reference y0
        sv = search(F1[0].astype(np.int64), refs[0], 8, 16, lev=0) if 'oracle' in modes else None
        row = {'ref': (b0, p0)}
        for m in modes:
            b, p, o, e, _ = code_frame(F1, refs, m, Qf, sh, lo, hi, depth, src_vec=sv)
            row[m] = (b, p, o, e); print(tag, Qf, m, '%.3f' % b, ' '.join('%.2f' % x for x in p), 'oor', o, 'g2', e, flush=True)
        out[str(Qf)] = row
    json.dump(out, open(tag + '.tp.json', 'w'))
